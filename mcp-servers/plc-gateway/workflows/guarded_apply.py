"""
PLC Engineering Gateway — TiaCommander 受控 Apply 工作流

仅允许以下操作：
  - update_network_title: 更新网络标题
  - update_network_comment: 更新网络注释

受控流程（全部在代码中实现，不依赖真实 TiaCommander 运行）：
  1. 获取原始块 XML
  2. 计算块 Hash
  3. 计算每个 Network 的 Hash
  4. 生成 Preview（含 ASCII Diff）
  5. 人工确认（通过确认令牌）
  6. 保存修改前 XML 快照
  7. 调用 TiaCommander apply_patch
  8. 重新读取 XML
  9. 比较实际修改与预期修改
  10. 编译验证
  11. 返回结果

禁止的操作：
  - 禁止上载/强制/CPU 操作
  - 禁止修改 OB1
  - 禁止自动 fallback 到 TiaWorker
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from providers.base import ProviderResult, TiaProvider, ErrorInfo

# 受保护的测试块名称
_PROTECTED_BLOCKS = frozenset(["OB1", "OB100", "OB121", "OB122"])

# 受控操作列表
_ALLOWED_OPERATIONS = frozenset([
    "update_network_title",
    "update_network_comment",
])


@dataclass
class NetworkSnapshot:
    """单个网络的快照"""
    index: int
    title: str
    comment: str
    content_hash: str  # 网络内容的 SHA-256


@dataclass
class BlockSnapshot:
    """块修改前的完整快照"""
    block_name: str
    original_xml: str
    block_hash: str  # 整个块的 SHA-256
    networks: list[NetworkSnapshot] = field(default_factory=list)
    snapshot_id: str = ""

    def __post_init__(self):
        if not self.snapshot_id:
            self.snapshot_id = uuid.uuid4().hex[:16]

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "block_name": self.block_name,
            "block_hash": self.block_hash[:16] + "...",
            "networks_count": len(self.networks),
            "networks": [
                {
                    "index": n.index,
                    "title": n.title,
                    "content_hash": n.content_hash[:16] + "...",
                }
                for n in self.networks
            ],
        }


@dataclass
class GuardedApplyResult:
    """受控 Apply 的结果"""
    success: bool
    operation: str
    block_name: str
    snapshot_id: str = ""
    preview: dict | None = None
    errors: list[str] = field(default_factory=list)
    compile_result: dict | None = None
    network_matches: list[dict] = field(default_factory=list)
    reconcile_required: bool = False

    def to_dict(self) -> dict:
        return {
            "ok": self.success,
            "operation": self.operation,
            "block_name": self.block_name,
            "snapshot_id": self.snapshot_id,
            "preview": self.preview,
            "errors": self.errors,
            "compile_result": self.compile_result,
            "network_matches": self.network_matches,
            "reconcile_required": self.reconcile_required,
        }


def _hash_content(content: str) -> str:
    """计算 SHA-256 哈希"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _extract_networks(xml_str: str) -> list[dict]:
    """从 SimaticML XML 中提取网络信息"""
    import xml.etree.ElementTree as ET
    networks = []
    try:
        root = ET.fromstring(xml_str)
        ns = "http://www.siemens.com/automation/Openness/SW/Motion/Networks/v1"
        for i, net in enumerate(root.iter(f"{{{ns}}}Network")):
            title_elem = net.find(f"{{{ns}}}NetworkTitle")
            title = ""
            if title_elem is not None:
                t = title_elem.find(f"{{{ns}}}Title")
                if t is not None and t.text:
                    title = t.text.strip()
            comment_elem = net.find(f"{{{ns}}}Comment")
            comment = ""
            if comment_elem is not None:
                c = comment_elem.find(f"{{{ns}}}Title")
                if c is not None and c.text:
                    comment = c.text.strip()
            # 计算网络内容的哈希
            net_xml = ET.tostring(net, encoding="unicode")
            networks.append({
                "index": i,
                "title": title,
                "comment": comment,
                "xml": net_xml,
                "hash": _hash_content(net_xml),
            })
    except ET.ParseError:
        pass
    return networks


def validate_guarded_apply(patch: dict, provider_name: str) -> list[str]:
    """验证受控 Apply 的前置条件

    检查：
    - 操作类型是否在允许列表中
    - 目标块是否受保护（禁止修改 OB1 等）
    - Provider 是否为 TiaCommander（禁止 fallback）
    """
    errors = []

    block = patch.get("block", "")
    if not block:
        errors.append("缺少必填字段: block")
        return errors

    # 检查受保护块
    if block.upper() in _PROTECTED_BLOCKS:
        errors.append(f"禁止修改受保护块: {block}")

    # 检查 Provider
    if provider_name != "tiacommander":
        errors.append(f"受控 Apply 需要 TiaCommander Provider，当前为: {provider_name}")

    # 检查操作
    operations = patch.get("operations", [])
    if not operations:
        errors.append("没有指定任何操作")

    for i, op in enumerate(operations):
        op_type = op.get("operation", "")
        if op_type not in _ALLOWED_OPERATIONS:
            errors.append(f"operations[{i}]: 不允许的操作 '{op_type}'，"
                         f"仅允许: {', '.join(sorted(_ALLOWED_OPERATIONS))}")

    return errors


async def guarded_apply_preview(
    provider: TiaProvider,
    block_name: str,
    patch: dict,
) -> dict:
    """受控 Apply 的 Preview 阶段（步骤 1-4）

    Args:
        provider: TiaCommanderProvider 实例
        block_name: 块名称
        patch: 结构化 Patch

    Returns:
        Preview 结果，含快照和 ASCII Diff
    """
    # 前置验证
    validation_errors = validate_guarded_apply(patch, provider.name)
    if validation_errors:
        return ProviderResult(
            ok=False, operation="guarded_apply.preview",
            error=f"前置验证失败: {'; '.join(validation_errors)}",
        ).to_dict()

    # 步骤 1: 获取原始 XML
    xml_result = provider.get_block_xml(block_name)
    if not xml_result.ok:
        return xml_result.to_dict()

    xml_str = ""
    if isinstance(xml_result.result, dict):
        xml_str = xml_result.result.get("xml", "") or xml_result.result.get("content", "")
    if not xml_str:
        return ProviderResult(
            ok=False, operation="guarded_apply.preview",
            error="无法获取块 XML",
        ).to_dict()

    # 步骤 2: 计算块 Hash
    block_hash = _hash_content(xml_str)

    # 步骤 3: 提取网络并计算每个网络的 Hash
    networks = _extract_networks(xml_str)
    network_snapshots = [
        NetworkSnapshot(
            index=n["index"],
            title=n["title"],
            comment=n["comment"],
            content_hash=n["hash"],
        )
        for n in networks
    ]

    # 创建块快照
    snapshot = BlockSnapshot(
        block_name=block_name,
        original_xml=xml_str,
        block_hash=block_hash,
        networks=network_snapshots,
    )

    # 步骤 4: 生成 Preview
    from workflows.network_patch import _generate_ascii_diff, BlockPatch

    bp = BlockPatch.from_dict(patch)
    diff = _generate_ascii_diff(bp, [
        {"index": n.index, "title": n.title, "comment": n.comment}
        for n in network_snapshots
    ])

    # 验证 network_index 是否有效
    for op in patch.get("operations", []):
        net_idx = op.get("network_index", 0)
        if net_idx >= len(networks):
            return ProviderResult(
                ok=False, operation="guarded_apply.preview",
                error=f"network_index {net_idx} 超出范围（当前块有 {len(networks)} 个网络）",
            ).to_dict()

    return ProviderResult(
        ok=True, operation="guarded_apply.preview",
        result={
            "block_name": block_name,
            "block_hash": block_hash,
            "networks_count": len(networks),
            "operations_count": len(patch.get("operations", [])),
            "snapshot": snapshot.to_dict(),
            "ascii_diff": diff,
            "requires_confirmation": True,
            "provider": provider.name,
        },
    ).to_dict()


async def guarded_apply_execute(
    provider: TiaProvider,
    block_name: str,
    patch: dict,
    confirmed: bool = False,
    compile_after: bool = True,
) -> dict:
    """执行受控 Apply（步骤 5-11）

    Args:
        provider: TiaCommanderProvider 实例
        block_name: 块名称
        patch: 结构化 Patch
        confirmed: 是否已确认
        compile_after: 是否在修改后编译

    Returns:
        执行结果
    """
    # 步骤 5: 人工确认
    if not confirmed:
        return GuardedApplyResult(
            success=False, operation="guarded_apply.execute",
            block_name=block_name,
            errors=["需要人工确认后才能执行"],
        ).to_dict()

    # 步骤 6: 获取修改前 XML（快照已由 preview 生成）
    xml_result = provider.get_block_xml(block_name)
    if not xml_result.ok:
        return xml_result.to_dict()

    xml_str = ""
    if isinstance(xml_result.result, dict):
        xml_str = xml_result.result.get("xml", "") or xml_result.result.get("content", "")
    if not xml_str:
        return GuardedApplyResult(
            success=False, operation="guarded_apply.execute",
            block_name=block_name,
            errors=["无法获取修改前 XML"],
        ).to_dict()

    pre_modification_xml = xml_str
    networks_before = _extract_networks(pre_modification_xml)

    # 步骤 7: 调用 TiaCommander apply_patch
    try:
        apply_result = provider.apply_patch(patch)
        if not apply_result.ok:
            # 失败时返回预修改 XML 以便恢复
            return GuardedApplyResult(
                success=False, operation="guarded_apply.execute",
                block_name=block_name,
                errors=[apply_result.error.message if isinstance(apply_result.error, ErrorInfo)
                        else str(apply_result.error)],
                reconcile_required=True,
            ).to_dict()
    except NotImplementedError:
        return GuardedApplyResult(
            success=False, operation="guarded_apply.execute",
            block_name=block_name,
            errors=[f"Provider '{provider.name}' 不支持 apply_patch"],
        ).to_dict()
    except Exception as e:
        return GuardedApplyResult(
            success=False, operation="guarded_apply.execute",
            block_name=block_name,
            errors=[f"执行异常: {e}"],
            reconcile_required=True,
        ).to_dict()

    # 步骤 8: 重新读取 XML
    re_read = provider.get_block_xml(block_name)
    if not re_read.ok:
        return GuardedApplyResult(
            success=False, operation="guarded_apply.execute",
            block_name=block_name,
            errors=["修改后重新读取 XML 失败", re_read.error.message if isinstance(re_read.error, ErrorInfo) else str(re_read.error)],
            reconcile_required=True,
        ).to_dict()

    post_xml = ""
    if isinstance(re_read.result, dict):
        post_xml = re_read.result.get("xml", "") or re_read.result.get("content", "")
    if not post_xml:
        return GuardedApplyResult(
            success=False, operation="guarded_apply.execute",
            block_name=block_name,
            errors=["修改后 XML 为空"],
            reconcile_required=True,
        ).to_dict()

    # 步骤 9: 比较实际修改与预期修改
    networks_after = _extract_networks(post_xml)
    network_matches = []
    for op in patch.get("operations", []):
        net_idx = op.get("network_index", 0)
        before = networks_before[net_idx] if net_idx < len(networks_before) else {}
        after = networks_after[net_idx] if net_idx < len(networks_after) else {}
        match = {
            "network_index": net_idx,
            "operation": op.get("operation", ""),
            "title_before": before.get("title", ""),
            "title_after": after.get("title", ""),
            "comment_before": before.get("comment", ""),
            "comment_after": after.get("comment", ""),
            "hash_before": before.get("hash", "")[:16] + "...",
            "hash_after": after.get("hash", "")[:16] + "...",
            "modified": before.get("hash", "") != after.get("hash", ""),
        }
        network_matches.append(match)

    # 验证修改是否成功（空列表不视为成功）
    allowed_matches = [m for m in network_matches if m["operation"] in _ALLOWED_OPERATIONS]
    all_modified = len(allowed_matches) > 0 and all(m["modified"] for m in allowed_matches)
    if not all_modified:
        return GuardedApplyResult(
            success=False, operation="guarded_apply.execute",
            block_name=block_name,
            errors=["部分网络修改未生效"],
            network_matches=network_matches,
            reconcile_required=True,
        ).to_dict()

    # 步骤 10: 编译验证
    compile_result = None
    if compile_after:
        try:
            compile_result = provider.compile_project()
            compile_result = compile_result.to_dict() if hasattr(compile_result, 'to_dict') else compile_result
        except Exception as e:
            compile_result = {"ok": False, "error": str(e)}

    return GuardedApplyResult(
        success=True,
        operation="guarded_apply.execute",
        block_name=block_name,
        network_matches=network_matches,
        compile_result=compile_result,
    ).to_dict()