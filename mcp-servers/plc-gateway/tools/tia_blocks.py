"""
PLC Engineering Gateway — 块分析工具

提供读取和理解 PLC 块逻辑的能力：
  - tia.block.get_xml: 获取块的原始 SimaticML XML
  - tia.block.describe: 解析块并生成结构化逻辑摘要
  - tia.block.get_call_graph: 获取块调用关系

核心处理链：
  TIA 块 → 导出 XML → XML Parser → LAD AST → ASCII-LAD → 逻辑摘要
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Any

from ..registry import (
    BLOCK_GET_XML, BLOCK_GET_INTERFACE, LAD_DESCRIBE,
    get_registry, register_tool,
)
from ..providers.base import ProviderResult, TiaProvider


def register_block_analysis_tools(registry=None) -> None:
    """注册块分析工具到注册表"""
    reg = registry or get_registry()
    for meta in [BLOCK_GET_XML, BLOCK_GET_INTERFACE, LAD_DESCRIBE]:
        try:
            reg.register(meta)
        except ValueError:
            pass


# ── XML 解析器 ──


def _safe_text(elem: ET.Element | None, default: str = "") -> str:
    return elem.text.strip() if elem is not None and elem.text else default


def _find(elem: ET.Element, path: str) -> ET.Element | None:
    """命名空间感知的 find"""
    return elem.find(path, _NS)


# XML 命名空间映射
_NS = {
    "": "http://www.siemens.com/automation/Openness/SW/Motion/Networks/v1",
    "sw": "http://www.siemens.com/automation/Openness/SW/Motion/Networks/v1",
    "eng": "http://www.siemens.com/automation/Openness/SW/Engineering/v1",
    "xml": "http://www.w3.org/XML/1998/namespace",
}


def _ns(tag: str) -> str:
    """添加默认命名空间前缀"""
    if "{" in tag:
        return tag
    return f"{{http://www.siemens.com/automation/Openness/SW/Motion/Networks/v1}}{tag}"


def _parse_simaticml_networks(xml_str: str) -> list[dict]:
    """解析 SimaticML XML 中的 Network 列表

    返回结构化的 Network 信息，包括编号、标题、指令和操作数。
    无法解析的指令标记为 unsupported。
    """
    networks = []
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as e:
        return [{"error": f"XML 解析失败: {e}"}]

    # 查找所有 Network
    for i, sw_block in enumerate(root.iter(_ns("SW.Blocks.PlcBlock"))):
        for network in sw_block.iter(_ns("Network")):
            net = {
                "index": len(networks),
                "title": "",
                "comment": "",
                "instructions": [],
                "operands": [],
                "calls": [],
            }
            # 标题
            title_elem = network.find("NetworkTitle")
            if title_elem is not None:
                net["title"] = _safe_text(title_elem.find("Title"))

            # 注释
            comment_elem = network.find("Comment")
            if comment_elem is not None:
                net["comment"] = _safe_text(comment_elem.find("Title"))

            # 解析指令（根据 LAD/FBD/SCL 不同结构）
            for member in network:
                tag = member.tag.split("}")[-1] if "}" in member.tag else member.tag
                if tag in ("NetworkTitle", "Comment"):
                    continue

                instr = {
                    "type": tag,
                    "unsupported": False,
                }
                # 尝试提取操作数
                operands = _extract_operands(member)
                if operands:
                    instr["operands"] = operands
                    net["operands"].extend(operands)

                # 尝试提取块调用
                if tag in ("Call", "CallInfo"):
                    call_name = _safe_text(member.find("Name"))
                    if call_name:
                        instr["call_name"] = call_name
                        net["calls"].append(call_name)
                    # 提取参数
                    params = _extract_call_params(member)
                    if params:
                        instr["parameters"] = params

                # 标记未知指令
                if tag not in ("LAD", "FBD", "SCL", "Call", "CallInfo",
                                "Contact", "Coil", "Branch", "Box", "Line",
                                "Powerrail", "NetworkTitle", "Comment"):
                    instr["unsupported"] = True

                net["instructions"].append(instr)

            networks.append(net)

    return networks


def _extract_operands(elem: ET.Element) -> list[dict]:
    """从 XML 元素中提取操作数"""
    operands = []
    for operand in elem.iter():
        tag = operand.tag.split("}")[-1] if "}" in operand.tag else operand.tag
        if tag in ("Operand", "Address", "Variable"):
            op = {
                "name": _safe_text(operand.find("Name") or operand),
                "address": _safe_text(operand.find("Address")),
                "type": _safe_text(operand.find("Type")),
            }
            if op["name"] or op["address"]:
                operands.append(op)
    return operands


def _extract_call_params(elem: ET.Element) -> list[dict]:
    """从调用元素中提取参数"""
    params = []
    for param in elem.iter():
        tag = param.tag.split("}")[-1] if "}" in param.tag else param.tag
        if tag == "Parameter":
            params.append({
                "name": _safe_text(param.find("Name")),
                "value": _safe_text(param.find("Value")),
                "address": _safe_text(param.find("Address")),
            })
    return params


def _generate_ascii_lad(networks: list[dict]) -> str:
    """从结构化 Network 信息生成简化的 ASCII-LAD 表示"""
    lines = []
    for net in networks:
        if "error" in net:
            lines.append(f"; 错误: {net['error']}")
            continue
        lines.append("")
        lines.append(f";═ Network {net['index']}: {net['title']}")
        if net["comment"]:
            lines.append(f";  {net['comment']}")
        for instr in net["instructions"]:
            if instr["unsupported"]:
                lines.append(f";  [未支持] {instr['type']}")
            elif instr["type"] == "Call":
                call_name = instr.get("call_name", "?")
                params = instr.get("parameters", [])
                param_str = ", ".join(
                    f"{p.get('name', '')}={p.get('value', '')}"
                    for p in params[:5]
                )
                if param_str:
                    lines.append(f"  CALL {call_name}({param_str})")
                else:
                    lines.append(f"  CALL {call_name}")
            elif instr.get("operands"):
                ops = ", ".join(
                    o.get("name", o.get("address", "?"))
                    for o in instr["operands"]
                )
                lines.append(f"  {instr['type']} {ops}")
            else:
                lines.append(f"  {instr['type']}")
        if net["calls"]:
            lines.append(f";  调用: {', '.join(net['calls'])}")
    return "\n".join(lines)


def _generate_summary(networks: list[dict]) -> str:
    """生成 AI 可读的逻辑摘要"""
    parts = []
    for net in networks:
        if "error" in net:
            parts.append(f"⚠ Network 解析失败: {net['error']}")
            continue
        title = net["title"] or f"Network {net['index']}"
        desc = f"  Network {net['index']}：{title}"
        if net["calls"]:
            desc += f" [调用: {', '.join(net['calls'])}]"
        parts.append(desc)
    return "\n".join(parts)


# ── MCP 工具函数 ──


async def tia_get_block_xml(provider: TiaProvider, block_name: str) -> dict:
    """获取块的原始 SimaticML XML

    Args:
        block_name: 块名称
    """
    result = provider.get_block_xml(block_name)
    return result.to_dict()


async def tia_describe_block_logic(provider: TiaProvider, block_name: str) -> dict:
    """解析块并生成结构化逻辑摘要

    返回原始 XML 和逻辑摘要，包含 Network 编号、标题、操作数和调用关系。

    Args:
        block_name: 块名称
    """
    # 获取块 XML
    xml_result = provider.get_block_xml(block_name)
    if not xml_result.ok:
        return xml_result.to_dict()

    xml_str = ""
    if isinstance(xml_result.result, dict):
        xml_str = xml_result.result.get("xml", "") or xml_result.result.get("content", "")
    if not xml_str:
        return ProviderResult(
            ok=False, operation="tia.block.describe",
            error="未能获取块 XML 内容",
        ).to_dict()

    # 解析 XML
    networks = _parse_simaticml_networks(xml_str)

    # 生成 ASCII-LAD
    ascii_lad = _generate_ascii_lad(networks)

    # 生成摘要
    summary = _generate_summary(networks)

    return ProviderResult(
        ok=True, operation="tia.block.describe",
        result={
            "block_name": block_name,
            "networks_count": len(networks),
            "networks": networks,
            "ascii_lad": ascii_lad,
            "summary": summary,
            "raw_xml": xml_str,
        },
    ).to_dict()


async def tia_get_call_graph(provider: TiaProvider, block_name: str) -> dict:
    """获取块的调用关系

    Args:
        block_name: 块名称
    """
    result = provider.get_block_xml(block_name)
    if not result.ok:
        return result.to_dict()

    xml_str = ""
    if isinstance(result.result, dict):
        xml_str = result.result.get("xml", "") or result.result.get("content", "")
    if not xml_str:
        return ProviderResult(
            ok=False, operation="tia.block.call_graph",
            error="未能获取块 XML 内容",
        ).to_dict()

    networks = _parse_simaticml_networks(xml_str)
    all_calls = set()
    callers = {}
    for net in networks:
        for call in net.get("calls", []):
            all_calls.add(call)
            if call not in callers:
                callers[call] = []
            callers[call].append(net.get("index", 0))

    return ProviderResult(
        ok=True, operation="tia.block.call_graph",
        result={
            "block_name": block_name,
            "calls": sorted(all_calls),
            "call_network_map": {k: v for k, v in callers.items()},
        },
    ).to_dict()