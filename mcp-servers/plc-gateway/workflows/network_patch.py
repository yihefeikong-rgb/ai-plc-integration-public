"""
PLC Engineering Gateway — 网络级 Patch 协议

提供结构化 Patch 的创建、预览、验证和应用能力。

标准流程：
  读取现有块 → 记录块 Hash → 生成 Patch → 显示 ASCII Diff
  → 自动导出修改前 XML → 用户确认 → 应用到复制项目
  → 编译 → 读取编译错误 → 成功后保存 → 失败则恢复旧 XML

Patch 结构：
  {
    "block": "MotorControl",
    "base_hash": "sha256...",
    "provider": "tiacommander",
    "operations": [
      {
        "operation": "update_network_title",
        "network_index": 3,
        "expected_network_hash": "sha256...",
        "new_title": "新标题"
      }
    ]
  }

支持的初始操作：
  - update_network_title: 更新网络标题
  - update_network_comment: 更新网络注释
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from plc_gateway.contracts.preview_apply import ApplyFailureState, get_preview_manager
from plc_gateway.providers.base import ProviderResult, TiaProvider

_logger = logging.getLogger(__name__)

# 支持的初始操作（逐步扩展）
_SUPPORTED_OPERATIONS = frozenset([
    "update_network_title",
    "update_network_comment",
])

# SHA-256 哈希正则
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")


# ── Patch Schema 验证 ──


_SCHEMA_CACHE: dict | None = None


def _load_schema() -> dict:
    """加载 JSON Schema（带缓存，避免每次校验重复读盘）"""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE
    schema_path = Path(__file__).parent.parent / "contracts" / "network_patch.schema.json"
    if schema_path.exists():
        _SCHEMA_CACHE = json.loads(schema_path.read_text(encoding="utf-8"))
    else:
        _SCHEMA_CACHE = {}
    return _SCHEMA_CACHE


def _schema_block_pattern() -> re.Pattern | None:
    """从 network_patch.schema.json 提取 block 名称格式正则

    Schema 缺失或 pattern 无效时返回 None（此时不做额外格式校验，
    但仍保留基础字段校验与 provider 白名单，保持 fail-closed）。
    """
    block = _load_schema().get("properties", {}).get("block", {})
    pattern = block.get("pattern", "")
    if not pattern:
        return None
    try:
        return re.compile(pattern)
    except re.error:
        _logger.warning("network_patch.schema.json 的 block.pattern 不是有效正则: %s", pattern)
        return None


def validate_patch(patch: dict) -> list[str]:
    """验证 Patch 结构，返回错误列表"""
    errors = []

    # 基本字段检查
    if not isinstance(patch, dict):
        return ["Patch 必须是 JSON 对象"]

    if "block" not in patch:
        errors.append("缺少必填字段: block")
    elif not isinstance(patch["block"], str) or not patch["block"].strip():
        errors.append("block 必须是有效的字符串")
    else:
        block_pattern = _schema_block_pattern()
        if block_pattern is not None and not block_pattern.fullmatch(patch["block"]):
            errors.append(f"block 必须匹配格式 {block_pattern.pattern}（来自 network_patch.schema.json）")

    if "base_hash" not in patch:
        errors.append("缺少必填字段: base_hash")
    elif not isinstance(patch["base_hash"], str) or not _HASH_PATTERN.match(patch["base_hash"]):
        errors.append("base_hash 必须是 64 字符的 SHA-256 十六进制字符串")

    if "operations" not in patch:
        errors.append("缺少必填字段: operations")
        return errors

    if not isinstance(patch["operations"], list) or len(patch["operations"]) == 0:
        errors.append("operations 必须是包含至少一个操作的非空数组")
        return errors

    # 验证每个操作
    for i, op in enumerate(patch["operations"]):
        op_errors = _validate_operation(op, i)
        errors.extend(op_errors)

    # Provider 检查（可选）
    provider = patch.get("provider", "")
    if provider and provider not in ("tiaworker", "tiacommander"):
        errors.append(f"不支持的 provider: {provider}（可选 tiaworker/tiacommander）")

    return errors


def _validate_operation(op: Any, index: int) -> list[str]:
    """验证单个操作"""
    errors = []
    prefix = f"operations[{index}]"

    if not isinstance(op, dict):
        return [f"{prefix}: 必须是 JSON 对象"]

    # operation 类型
    op_type = op.get("operation", "")
    if not op_type:
        errors.append(f"{prefix}: 缺少必填字段 operation")
    elif op_type not in _SUPPORTED_OPERATIONS:
        supported = ", ".join(sorted(_SUPPORTED_OPERATIONS))
        errors.append(f"{prefix}: 不支持的操作 '{op_type}'，支持: {supported}")

    # network_index
    net_idx = op.get("network_index")
    if net_idx is None:
        errors.append(f"{prefix}: 缺少必填字段 network_index")
    elif not isinstance(net_idx, int) or net_idx < 0:
        errors.append(f"{prefix}: network_index 必须是非负整数")

    # expected_network_hash（可选）
    net_hash = op.get("expected_network_hash", "")
    if net_hash and (not isinstance(net_hash, str) or not _HASH_PATTERN.match(net_hash)):
        errors.append(f"{prefix}: expected_network_hash 必须是 64 字符的 SHA-256 字符串")

    # 操作特定验证
    if op_type == "update_network_title" and not op.get("new_title"):
        errors.append(f"{prefix}: update_network_title 需要提供 new_title")

    if op_type == "update_network_comment" and not op.get("new_comment"):
        errors.append(f"{prefix}: update_network_comment 需要提供 new_comment")

    return errors


# ── 数据类 ──


@dataclass
class NetworkOperation:
    """单个网络级操作"""
    operation: str
    network_index: int
    expected_network_hash: str = ""
    new_network: dict | None = None
    new_title: str = ""
    new_comment: str = ""


@dataclass
class BlockPatch:
    """结构化块 Patch"""
    block: str
    base_hash: str
    provider: str = ""
    operations: list[NetworkOperation] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "BlockPatch":
        """从字典创建 BlockPatch，缺失字段使用默认值"""
        if not isinstance(data, dict):
            raise ValueError("BlockPatch.from_dict 需要 dict 类型参数")
        return cls(
            block=data.get("block", ""),
            base_hash=data.get("base_hash", ""),
            provider=data.get("provider", ""),
            operations=[
                NetworkOperation(
                    operation=op.get("operation", ""),
                    network_index=op.get("network_index", 0),
                    expected_network_hash=op.get("expected_network_hash", ""),
                    new_network=op.get("new_network"),
                    new_title=op.get("new_title", ""),
                    new_comment=op.get("new_comment", ""),
                )
                for op in data.get("operations", [])
            ],
        )

    def to_dict(self) -> dict:
        return {
            "block": self.block,
            "base_hash": self.base_hash,
            "provider": self.provider,
            "operations": [
                {
                    "operation": op.operation,
                    "network_index": op.network_index,
                    "expected_network_hash": op.expected_network_hash,
                    "new_network": op.new_network,
                    "new_title": op.new_title,
                    "new_comment": op.new_comment,
                }
                for op in self.operations
            ],
        }


# ── 工具函数 ──


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _extract_networks_from_xml(xml_str: str) -> list[dict] | None:
    """从 XML 中提取网络信息

    Returns:
        网络列表；XML 解析失败时记录日志并返回 None（调用方必须 fail-closed）。
    """
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
            networks.append({
                "index": i,
                "title": title,
                "comment": comment,
            })
    except ET.ParseError as e:
        _logger.error("解析块 XML 失败（返回 None，调用方应拒绝继续）: %s", e)
        return None
    return networks


def _generate_ascii_diff(patch: BlockPatch, current_networks: list[dict]) -> str:
    """生成人类可读的 ASCII Diff 预览"""
    lines = []
    lines.append(f"块: {patch.block}")
    lines.append(f"Base Hash: {patch.base_hash[:16]}...")
    if patch.provider:
        lines.append(f"Provider: {patch.provider}")
    lines.append("")

    for op in patch.operations:
        current = {}
        if op.network_index < len(current_networks):
            current = current_networks[op.network_index]

        if op.operation == "update_network_title":
            old_title = current.get("title", "")
            lines.append(f"~~~ Network {op.network_index}")
            lines.append(f"    - 标题: {old_title or '(空)'}")
            lines.append(f"    + 标题: {op.new_title}")

        elif op.operation == "update_network_comment":
            old_comment = current.get("comment", "")
            lines.append(f"~~~ Network {op.network_index}")
            lines.append(f"    - 注释: {old_comment or '(空)'}")
            lines.append(f"    + 注释: {op.new_comment}")

        elif op.operation == "delete_network":
            lines.append(f"--- Network {op.network_index}: {current.get('title', '')}")
            lines.append(f"+++ (删除)")

        elif op.operation == "replace_network":
            lines.append(f"--- Network {op.network_index}: {current.get('title', '')}")
            lines.append(f"+++ (替换)")
            if op.new_network:
                lines.append(f"    新标题: {op.new_network.get('title', '')}")

        elif op.operation == "insert_network":
            lines.append(f"+++ Network {op.network_index} (插入)")
            if op.new_network:
                lines.append(f"    标题: {op.new_network.get('title', '')}")

        if op.expected_network_hash:
            lines.append(f"    预期 Hash: {op.expected_network_hash[:16]}...")

        lines.append("")

    return "\n".join(lines)


async def tia_preview_block_patch(
    provider: TiaProvider,
    block_name: str,
    patch: dict,
) -> dict:
    """预览块 Patch 的效果（含严格验证）

    Args:
        block_name: 块名称
        patch: 结构化 Patch 字典

    Returns:
        预览结果，包含：
        - 验证结果
        - base_hash 匹配检查
        - ASCII Diff
        - 操作统计
        - 风险等级建议
    """
    # 1. 严格验证 Patch 结构
    validation_errors = validate_patch(patch)
    if validation_errors:
        return ProviderResult(
            ok=False, operation="tia.block.preview_patch",
            error=f"Patch 验证失败: {'; '.join(validation_errors)}",
        ).to_dict()

    # 1.1 块名格式与目标一致性校验（防止预览 A 块而操作 B 块）
    block_pattern = _schema_block_pattern()
    if block_pattern is not None and not block_pattern.fullmatch(block_name):
        return ProviderResult(
            ok=False, operation="tia.block.preview_patch",
            error=f"block_name 必须匹配格式 {block_pattern.pattern}（来自 network_patch.schema.json）",
        ).to_dict()
    if patch.get("block", "") != block_name:
        return ProviderResult(
            ok=False, operation="tia.block.preview_patch",
            error="patch.block 与 block_name 不一致，拒绝预览（预览目标必须与操作目标一致）",
        ).to_dict()

    # 2. 获取当前块 XML
    xml_result = provider.get_block_xml(block_name)
    if not xml_result.ok:
        return xml_result.to_dict()

    xml_str = ""
    if isinstance(xml_result.result, dict):
        xml_str = xml_result.result.get("xml", "") or xml_result.result.get("content", "")
    if not xml_str:
        return ProviderResult(
            ok=False, operation="tia.block.preview_patch",
            error="无法获取块 XML，拒绝预览",
        ).to_dict()

    current_hash = _hash_content(xml_str)

    # 3. 验证 base_hash
    patch_base = patch.get("base_hash", "")
    if current_hash and patch_base and current_hash != patch_base:
        return ProviderResult(
            ok=False, operation="tia.block.preview_patch",
            error=f"Base hash 不匹配：当前 {current_hash[:16]}...，预期 {patch_base[:16]}...。块已被修改，请重新读取。",
            reconcile_required=True,
        ).to_dict()

    # 4. 提取当前网络信息
    networks = _extract_networks_from_xml(xml_str)
    if networks is None:
        return ProviderResult(
            ok=False, operation="tia.block.preview_patch",
            error="块 XML 解析失败，拒绝预览（详见日志）",
        ).to_dict()

    # 5. 验证 network_index 是否有效
    for op in patch.get("operations", []):
        net_idx = op.get("network_index", 0)
        if net_idx >= len(networks):
            return ProviderResult(
                ok=False, operation="tia.block.preview_patch",
                error=f"network_index {net_idx} 超出范围（当前块有 {len(networks)} 个网络）",
            ).to_dict()

    # 6. 构建 BlockPatch
    bp = BlockPatch.from_dict(patch)

    # 7. 生成 ASCII Diff
    diff = _generate_ascii_diff(bp, networks)

    # 8. 计算预览元数据
    risk_level = "L2"  # 网络元数据修改为 L2 风险
    requires_confirmation = True

    # 操作摘要
    op_summary = []
    for op in patch.get("operations", []):
        net_idx = op.get("network_index", 0)
        op_type = op.get("operation", "")
        current = networks[net_idx] if net_idx < len(networks) else {}
        summary = {
            "operation": op_type,
            "network_index": net_idx,
            "original_title": current.get("title", ""),
            "original_comment": current.get("comment", ""),
        }
        if op_type == "update_network_title":
            summary["new_title"] = op.get("new_title", "")
        elif op_type == "update_network_comment":
            summary["new_comment"] = op.get("new_comment", "")
        op_summary.append(summary)

    return ProviderResult(
        ok=True, operation="tia.block.preview_patch",
        result={
            "block_name": block_name,
            "current_hash": current_hash,
            "networks_count": len(networks),
            "operations_count": len(bp.operations),
            "risk_level": risk_level,
            "requires_confirmation": requires_confirmation,
            "provider": provider.name,
            "ascii_diff": diff,
            "operations": op_summary,
            "patch": bp.to_dict(),
        },
    ).to_dict()


async def tia_apply_block_patch(
    provider: TiaProvider,
    block_name: str,
    patch: dict,
    confirmation_token: str = "",
    project_path: str = "",
    target_hash: str = "",
    device_id: str = "",
) -> dict:
    """应用块 Patch

    安全要求（fail-closed）：
    - 必须先预览：预览阶段强制校验 patch.block 与 block_name 一致、
      base_hash 匹配与 network_index 越界；
    - 必须提供一次性确认令牌：由 PreviewManager 签发（HMAC 签名并绑定
      项目/目标 Hash/设备），此处消费并写入审计链；缺失、未签名或校验
      失败一律拒绝，不允许绕过（GATEWAY_SAFETY_ENABLED=0 时令牌无签名，
      同样被拒，保持关闭安全链也不放行写入）；
    - 在一次性消费确认令牌之前重新读取块并核对 Hash，防止预览后到执行前
      的 TOCTOU 漂移；块漂移时拒绝执行且不消费令牌，避免确认被无谓烧毁。

    Args:
        block_name: 块名称
        patch: 结构化 Patch 字典
        confirmation_token: 人工确认后由 PreviewManager 签发的确认令牌
        project_path: 项目路径（确认令牌绑定项，可选）
        target_hash: 预览时的块 Hash（确认令牌绑定项，可选，默认取本次预览值）
        device_id: 设备 ID（确认令牌绑定项，可选）
    """
    # 0. 确认令牌强制（registry L2 元数据 requires_confirmation=True）
    if not confirmation_token:
        return ProviderResult(
            ok=False, operation="tia.block.apply_patch",
            error="操作必须人工确认（缺少确认令牌）",
        ).to_dict()

    # 1. 预览（严格验证，含 block 一致性、base_hash 与 network_index）
    result = await tia_preview_block_patch(provider, block_name, patch)
    if not result.get("ok"):
        return result

    result_data = result.get("result", {}) or {}
    current_hash = result_data.get("current_hash", "")

    mgr = get_preview_manager()

    # 2. TOCTOU 防护：在一次性消费确认令牌之前重新读取块，Hash 必须与预览一致。
    #    消费令牌是不可逆的一次性操作，必须等复读确认通过后再执行；否则块在
    #    预览后漂移时确认令牌会被无谓烧毁，审计还会留下缺 APPLY_STARTED 的
    #    TOKEN_CONSUMED→APPLY_FAILED 序列。漂移时令牌保持未消费（可重新预览
    #    确认，或在块状态恢复后复用原确认）；此处仅用 validate_token 取得令牌
    #    引用用于审计记录，不标记 used。
    xml_result = provider.get_block_xml(block_name)
    if not xml_result.ok:
        return xml_result.to_dict()
    xml_str = ""
    if isinstance(xml_result.result, dict):
        xml_str = xml_result.result.get("xml", "") or xml_result.result.get("content", "")
    if not xml_str or _hash_content(xml_str) != current_hash:
        drift_token = mgr.validate_token(
            confirmation_token,
            project_path,
            target_hash or current_hash,
            device_id,
        )
        if drift_token is not None:
            mgr.apply_failed(drift_token, "块内容在预览后改变，拒绝执行",
                             ApplyFailureState.RECONCILE_REQUIRED)
        return ProviderResult(
            ok=False, operation="tia.block.apply_patch",
            error="块内容在预览后改变，拒绝执行（请重新预览并确认）",
            reconcile_required=True,
        ).to_dict()

    # 3. 一次性消费确认令牌并校验签名（fail-closed，消费即写入审计链）
    token = mgr.consume_token(
        confirmation_token,
        project_path,
        target_hash or current_hash,
        device_id,
    )
    if token is None:
        return ProviderResult(
            ok=False, operation="tia.block.apply_patch",
            error="确认令牌无效、已使用、已过期或与项目/目标/设备绑定不符",
            reconcile_required=True,
        ).to_dict()
    if not token.signature:
        return ProviderResult(
            ok=False, operation="tia.block.apply_patch",
            error="确认令牌未签名（HMAC 认证未生效），拒绝应用",
            reconcile_required=True,
        ).to_dict()

    # 4. 执行应用（记录审计链）
    mgr.apply_started(token)
    try:
        provider_result = provider.apply_patch(patch)
    except NotImplementedError:
        mgr.apply_failed(token, f"Provider '{provider.name}' 不支持网络级修改")
        return ProviderResult(
            ok=False, operation="tia.block.apply_patch",
            error=f"Provider '{provider.name}' 不支持网络级修改。"
                  f"此功能需要 TiaCommander 或 TiaWorker 的扩展支持。",
            reconcile_required=True,
        ).to_dict()
    except Exception as e:
        mgr.apply_failed(token, f"执行异常: {e}")
        return ProviderResult(
            ok=False, operation="tia.block.apply_patch",
            error=f"执行异常: {e}",
            reconcile_required=True,
        ).to_dict()

    if not provider_result.ok:
        detail = provider_result.error.message if provider_result.error else "应用失败"
        mgr.apply_failed(token, detail)
        return provider_result.to_dict()

    mgr.apply_succeeded(token, f"已应用 {len(patch.get('operations', []))} 个网络操作")
    return provider_result.to_dict()
