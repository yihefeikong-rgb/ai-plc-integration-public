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
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from plc_gateway.contracts.preview_apply import ApplyFailureState, get_preview_manager
from plc_gateway.providers.base import ProviderResult, TiaProvider, ErrorInfo

_logger = logging.getLogger(__name__)

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
            "block_hash_full": self.block_hash,
            "networks_count": len(self.networks),
            "networks": [
                {
                    "index": n.index,
                    "title": n.title,
                    "content_hash": n.content_hash[:16] + "...",
                    "content_hash_full": n.content_hash,
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
    except ET.ParseError as e:
        _logger.error("解析块 XML 失败（返回空网络列表）: %s", e)
    return networks


def validate_guarded_apply(patch: dict, provider_name: str) -> list[str]:
    """验证受控 Apply 的前置条件

    检查：
    - Patch 必须是 JSON 对象
    - 操作类型是否在允许列表中
    - network_index 是否存在且为非负整数（bool 视为非法）
    - 目标块是否受保护（禁止修改 OB1 等）
    - Provider 是否为 TiaCommander（禁止 fallback）
    """
    errors = []

    if not isinstance(patch, dict):
        return ["Patch 必须是 JSON 对象"]

    block = patch.get("block", "")
    if not isinstance(block, str) or not block:
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
    if not isinstance(operations, list):
        errors.append("operations 必须是数组")
        return errors
    if not operations:
        errors.append("没有指定任何操作")

    for i, op in enumerate(operations):
        if not isinstance(op, dict):
            errors.append(f"operations[{i}]: 必须是 JSON 对象")
            continue

        op_type = op.get("operation", "")
        if op_type not in _ALLOWED_OPERATIONS:
            errors.append(f"operations[{i}]: 不允许的操作 '{op_type}'，"
                         f"仅允许: {', '.join(sorted(_ALLOWED_OPERATIONS))}")

        # network_index 必须存在且为非负整数（bool 是 int 的子类，视为非法）
        net_idx = op.get("network_index")
        if net_idx is None:
            errors.append(f"operations[{i}]: 缺少必填字段 network_index")
        elif isinstance(net_idx, bool) or not isinstance(net_idx, int) or net_idx < 0:
            errors.append(f"operations[{i}]: network_index 必须是非负整数")

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
    from plc_gateway.workflows.network_patch import _generate_ascii_diff, BlockPatch

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
        confirmation_token: str = "",
        compile_after: bool = True,
        snapshot: BlockSnapshot | None = None,
        project_path: str = "",
) -> dict:
    """执行受控 Apply（步骤 5-11）

    Args:
        provider: TiaCommanderProvider 实例
        block_name: 块名称
        patch: 结构化 Patch
        confirmation_token: 人工确认后由 PreviewManager 签发的一次性确认令牌
            （布尔 confirmed 不构成确认证据，不再接受布尔放行——
            与 safety_chain.check_confirmation 的 fail-closed 语义一致）
        compile_after: 是否在修改后编译
        snapshot: guarded_apply_preview 生成的块快照（必填，用于 TOCTOU 防护）
        project_path: 当前项目路径（确认令牌绑定项；令牌绑定了项目路径
            而执行方未提供当前值时按 fail-closed 拒绝）

    Returns:
        执行结果
    """
    # 步骤 5: 人工确认（fail-closed：必须提供一次性确认令牌）
    if not confirmation_token:
        return GuardedApplyResult(
            success=False, operation="guarded_apply.execute",
            block_name=block_name,
            errors=["操作必须人工确认（缺少确认令牌）"],
        ).to_dict()

    # 前置验证：执行阶段必须重新校验受保护块与允许操作白名单
    validation_errors = validate_guarded_apply(patch, provider.name)
    if validation_errors:
        return GuardedApplyResult(
            success=False, operation="guarded_apply.execute",
            block_name=block_name,
            errors=[f"前置验证失败: {'; '.join(validation_errors)}"],
        ).to_dict()

    # 步骤 6: 获取修改前 XML（快照已由 preview 生成）
    if snapshot is None:
        return GuardedApplyResult(
            success=False, operation="guarded_apply.execute",
            block_name=block_name,
            errors=["缺少 preview 生成的快照，受控 Apply 必须先预览再执行"],
        ).to_dict()

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

    # TOCTOU 防护：当前块哈希必须与 preview 快照一致，否则拒绝执行
    current_block_hash = _hash_content(xml_str)
    if snapshot.block_hash != current_block_hash:
        return GuardedApplyResult(
            success=False, operation="guarded_apply.execute",
            block_name=block_name,
            errors=[
                f"块内容已在预览后改变（快照哈希 {snapshot.block_hash[:16]}...，"
                f"当前 {current_block_hash[:16]}...），拒绝执行",
            ],
            reconcile_required=True,
        ).to_dict()

    # 复用 preview 快照的解析结果，避免重复全树解析与逐网络哈希
    networks_before = [
        {
            "index": n.index,
            "title": n.title,
            "comment": n.comment,
            "hash": n.content_hash,
        }
        for n in snapshot.networks
    ]

    # 校验每个操作的 expected_network_hash（如提供）与当前网络实际哈希一致
    for i, op in enumerate(patch.get("operations", [])):
        net_idx = op.get("network_index", 0)
        expected = op.get("expected_network_hash", "")
        if not expected:
            continue
        before = networks_before[net_idx] if net_idx < len(networks_before) else {}
        if before.get("hash", "") != expected:
            return GuardedApplyResult(
                success=False, operation="guarded_apply.execute",
                block_name=block_name,
                errors=[
                    f"operations[{i}] network_index {net_idx} 的 expected_network_hash "
                    f"与实际内容哈希不一致，拒绝执行",
                ],
                reconcile_required=True,
            ).to_dict()

    # 步骤 6.5: 一次性消费确认令牌（全部只读检查——前置验证 / 快照 /
    # TOCTOU / expected_network_hash——通过之后才消费，顺序对照
    # network_patch.apply_block_patch；消费失败或未签名一律拒绝）
    mgr = get_preview_manager()
    token = mgr.consume_token(confirmation_token, project_path)
    if token is None:
        return GuardedApplyResult(
            success=False, operation="guarded_apply.execute",
            block_name=block_name,
            errors=["确认令牌无效、已使用、已过期或与项目/目标/设备绑定不符"],
            reconcile_required=True,
        ).to_dict()
    if not token.signature:
        return GuardedApplyResult(
            success=False, operation="guarded_apply.execute",
            block_name=block_name,
            errors=["确认令牌未签名（HMAC 认证未生效），拒绝应用"],
            reconcile_required=True,
        ).to_dict()

    # 步骤 7: 调用 TiaCommander apply_patch（记录审计链）
    mgr.apply_started(token)
    try:
        apply_result = provider.apply_patch(patch)
        if not apply_result.ok:
            # 失败时返回预修改 XML 以便恢复
            error = apply_result.error.message if isinstance(apply_result.error, ErrorInfo) \
                else str(apply_result.error)
            mgr.apply_failed(token, error)
            return GuardedApplyResult(
                success=False, operation="guarded_apply.execute",
                block_name=block_name,
                errors=[error],
                reconcile_required=True,
            ).to_dict()
    except NotImplementedError:
        mgr.apply_failed(token, f"Provider '{provider.name}' 不支持 apply_patch")
        return GuardedApplyResult(
            success=False, operation="guarded_apply.execute",
            block_name=block_name,
            errors=[f"Provider '{provider.name}' 不支持 apply_patch"],
        ).to_dict()
    except Exception as e:
        mgr.apply_failed(token, f"执行异常: {e}")
        return GuardedApplyResult(
            success=False, operation="guarded_apply.execute",
            block_name=block_name,
            errors=[f"执行异常: {e}"],
            reconcile_required=True,
        ).to_dict()

    # 步骤 8: 重新读取 XML
    re_read = provider.get_block_xml(block_name)
    if not re_read.ok:
        mgr.apply_failed(token, "修改后重新读取 XML 失败",
                         ApplyFailureState.RECONCILE_REQUIRED)
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
        mgr.apply_failed(token, "修改后 XML 为空",
                         ApplyFailureState.RECONCILE_REQUIRED)
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
        mgr.apply_failed(token, "部分网络修改未生效",
                         ApplyFailureState.RECONCILE_REQUIRED)
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

    # 编译失败视为整体失败（fail-closed），不得以 success=True 返回
    if compile_result is not None and not compile_result.get("ok"):
        compile_err = compile_result.get("error", "")
        mgr.apply_failed(token, f"编译验证失败: {compile_err}" if compile_err else "编译验证失败",
                         ApplyFailureState.RECONCILE_REQUIRED)
        return GuardedApplyResult(
            success=False, operation="guarded_apply.execute",
            block_name=block_name,
            errors=[f"编译验证失败: {compile_err}" if compile_err else "编译验证失败"],
            network_matches=network_matches,
            compile_result=compile_result,
            reconcile_required=True,
        ).to_dict()

    mgr.apply_succeeded(token, f"已应用 {len(patch.get('operations', []))} 个网络操作")
    return GuardedApplyResult(
        success=True,
        operation="guarded_apply.execute",
        block_name=block_name,
        network_matches=network_matches,
        compile_result=compile_result,
    ).to_dict()
