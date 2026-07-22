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
    "operations": [
      {
        "operation": "replace_network",
        "network_index": 3,
        "expected_network_hash": "sha256...",
        "new_network": {}
      }
    ]
  }
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from ..providers.base import ProviderResult, TiaProvider


@dataclass
class NetworkOperation:
    """单个网络级操作"""
    operation: str  # insert_network, replace_network, delete_network, update_metadata
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
    operations: list[NetworkOperation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "block": self.block,
            "base_hash": self.base_hash,
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


def _hash_content(content: str) -> str:
    """计算内容的 SHA-256 哈希"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _generate_ascii_diff(patch: BlockPatch, current_networks: list[dict]) -> str:
    """生成人类可读的 ASCII Diff 预览"""
    lines = []
    lines.append(f"块: {patch.block}")
    lines.append(f"Base Hash: {patch.base_hash[:16]}...")
    lines.append("")

    for op in patch.operations:
        current = {}
        if op.network_index < len(current_networks):
            current = current_networks[op.network_index]

        if op.operation == "delete_network":
            lines.append(f"--- Network {op.network_index}: {current.get('title', '')}")
            lines.append(f"+++ (删除)")
            lines.append(f"    当前 Hash: {op.expected_network_hash[:16]}...")

        elif op.operation == "replace_network":
            lines.append(f"--- Network {op.network_index}: {current.get('title', '')}")
            lines.append(f"+++ (替换)")
            if op.new_network:
                lines.append(f"    新标题: {op.new_network.get('title', '')}")

        elif op.operation == "insert_network":
            lines.append(f"+++ Network {op.network_index} (插入)")
            if op.new_network:
                lines.append(f"    标题: {op.new_network.get('title', '')}")

        elif op.operation == "update_metadata":
            lines.append(f"~~~ Network {op.network_index}: {current.get('title', '')}")
            if op.new_title:
                lines.append(f"    新标题: {op.new_title}")
            if op.new_comment:
                lines.append(f"    新注释: {op.new_comment}")

        lines.append("")

    return "\n".join(lines)


async def tia_preview_block_patch(
    provider: TiaProvider,
    block_name: str,
    patch: dict,
) -> dict:
    """预览块 Patch 的效果

    Args:
        block_name: 块名称
        patch: 结构化 Patch 字典
    """
    # 获取当前块 XML
    xml_result = provider.get_block_xml(block_name)
    if not xml_result.ok:
        return xml_result.to_dict()

    xml_str = ""
    if isinstance(xml_result.result, dict):
        xml_str = xml_result.result.get("xml", "") or xml_result.result.get("content", "")

    current_hash = _hash_content(xml_str) if xml_str else ""

    # 验证 base_hash
    patch_base = patch.get("base_hash", "")
    if current_hash and patch_base and current_hash != patch_base:
        return ProviderResult(
            ok=False, operation="tia.block.preview_patch",
            error=f"Base hash 不匹配：当前 {current_hash[:16]}...，预期 {patch_base[:16]}...。块已被修改，请重新读取。",
            reconcile_required=True,
        ).to_dict()

    # 生成 Diff 预览
    # 简单解析当前网络信息
    networks = []
    if xml_str:
        import xml.etree.ElementTree as ET
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
                networks.append({"index": i, "title": title})
        except ET.ParseError:
            pass

    bp = BlockPatch(
        block=block_name,
        base_hash=patch.get("base_hash", ""),
        operations=[
            NetworkOperation(
                operation=op["operation"],
                network_index=op.get("network_index", 0),
                expected_network_hash=op.get("expected_network_hash", ""),
                new_network=op.get("new_network"),
                new_title=op.get("new_title", ""),
                new_comment=op.get("new_comment", ""),
            )
            for op in patch.get("operations", [])
        ],
    )

    diff = _generate_ascii_diff(bp, networks)

    return ProviderResult(
        ok=True, operation="tia.block.preview_patch",
        result={
            "block_name": block_name,
            "current_hash": current_hash,
            "operations_count": len(bp.operations),
            "ascii_diff": diff,
            "patch": bp.to_dict(),
        },
    ).to_dict()


async def tia_apply_block_patch(
    provider: TiaProvider,
    block_name: str,
    patch: dict,
) -> dict:
    """应用块 Patch

    Args:
        block_name: 块名称
        patch: 结构化 Patch 字典
    """
    result = await tia_preview_block_patch(provider, block_name, patch)
    if not result.get("ok"):
        return result

    # 实际应用中，这里会调用 provider 的 apply_patch
    # 目前 TiaWorker 不支持直接网络级修改，返回功能说明
    try:
        provider_result = provider.apply_patch(patch)
        return provider_result.to_dict()
    except NotImplementedError:
        return ProviderResult(
            ok=False, operation="tia.block.apply_patch",
            error=f"Provider '{provider.name}' 不支持网络级修改。"
                  f"此功能需要 TiaCommander 或 TiaWorker 的扩展支持。",
        ).to_dict()