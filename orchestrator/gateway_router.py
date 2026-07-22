"""
PLC Engineering Gateway Router — 编排层网关路由

管理 PLC Gateway 与旧 MCP 服务器的路由决策和阴影比较。

路由模式：
  shadow（默认）— 同时调用 Gateway 和旧 MCP，比较结果但不影响主流程
  primary — Gateway 接管 TIA 只读操作，旧 MCP 作为 fallback
  off — 不启用 Gateway
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

_logger = logging.getLogger(__name__)

# TIA 只读操作映射：工具名 -> 对应旧 MCP 服务器
_TIA_READ_OPS: dict[str, str] = {
    "tia.project.info": "tia-mcp",
    "tia.project.list": "tia-mcp",
    "tia.block.list": "tia-mcp",
    "tia.block.get_xml": "tia-mcp",
    "tia.block.get_interface": "tia-mcp",
    "tia.hardware.list": "tia-mcp",
}


def is_tia_read_operation(tool_name: str) -> bool:
    """判断是否为 TIA 只读操作"""
    return tool_name in _TIA_READ_OPS


def get_legacy_server(tool_name: str) -> str | None:
    """获取 TIA 只读操作对应的旧 MCP 服务器名"""
    return _TIA_READ_OPS.get(tool_name)


async def call_gateway(pool, tool_name: str, arguments: dict | None = None) -> dict | None:
    """调用 Gateway 的工具，失败时返回 None"""
    try:
        result = await pool.call_tool("plc-gateway", tool_name, arguments or {})
        return result
    except Exception as e:
        _logger.warning(f"Gateway 调用失败 ({tool_name}): {e}")
        return None


async def call_legacy(pool, tool_name: str, arguments: dict | None = None) -> dict | None:
    """调用旧 MCP 服务器的工具，失败时返回 None"""
    server = get_legacy_server(tool_name)
    if not server:
        return None
    try:
        result = await pool.call_tool(server, tool_name, arguments or {})
        return result
    except Exception as e:
        _logger.warning(f"旧 MCP 调用失败 ({server}.{tool_name}): {e}")
        return None


def compare_results(gateway_result: dict | None, legacy_result: dict | None) -> dict:
    """比较 Gateway 和旧 MCP 的结果差异"""
    # 提取语义关键字段进行比较
    gw_ok = gateway_result is not None and gateway_result.get("ok", False)
    legacy_ok = legacy_result is not None

    comparison = {
        "gateway_ok": gw_ok,
        "legacy_ok": legacy_ok,
        "semantic_match": False,
        "differences": [],
    }

    if gw_ok and legacy_ok:
        # 比较结果中的关键字段
        gw_data = gateway_result.get("result", {}) or {}
        legacy_data = legacy_result

        # 对于块列表，比较数量
        if isinstance(gw_data, dict) and isinstance(legacy_data, dict):
            gw_keys = set(gw_data.keys())
            legacy_keys = set(legacy_data.keys())
            if gw_keys != legacy_keys:
                comparison["differences"].append(
                    f"字段差异: Gateway={gw_keys}, Legacy={legacy_keys}")
            else:
                comparison["semantic_match"] = True
        elif isinstance(gw_data, list) and isinstance(legacy_data, list):
            if len(gw_data) == len(legacy_data):
                comparison["semantic_match"] = True
            else:
                comparison["differences"].append(
                    f"数量差异: Gateway={len(gw_data)}, Legacy={len(legacy_data)}")
    elif gw_ok and not legacy_ok:
        comparison["differences"].append("Gateway 成功但旧 MCP 失败")
    elif not gw_ok and legacy_ok:
        comparison["differences"].append("旧 MCP 成功但 Gateway 失败")

    return comparison


async def route_tia_read(pool, tool_name: str, arguments: dict | None = None,
                         mode: str = "shadow") -> dict:
    """路由 TIA 只读操作

    Args:
        pool: MCP 连接池
        tool_name: 工具名
        arguments: 工具参数
        mode: 路由模式（shadow/primary/off）

    Returns:
        操作结果
    """
    if mode == "off":
        # 直接调用旧 MCP
        result = await call_legacy(pool, tool_name, arguments)
        if result is None:
            return {"ok": False, "error": f"旧 MCP 不可用: {tool_name}"}
        return result

    if mode == "shadow":
        # 并行调用 Gateway 和旧 MCP
        gw_task = call_gateway(pool, tool_name, arguments)
        legacy_task = call_legacy(pool, tool_name, arguments)
        gw_result, legacy_result = await asyncio.gather(gw_task, legacy_task)

        # 比较结果
        comparison = compare_results(gw_result, legacy_result)
        if comparison["differences"]:
            _logger.warning(f"Gateway 阴影比较发现差异 [{tool_name}]: "
                           f"{comparison['differences']}")

        # 阴影模式返回旧 MCP 结果
        if legacy_result is not None:
            return legacy_result
        if gw_result is not None:
            _logger.info(f"Gateway 阴影模式提供 fallback: {tool_name}")
            return gw_result
        return {"ok": False, "error": f"Gateway 和旧 MCP 均不可用: {tool_name}"}

    if mode == "primary":
        # Gateway 优先
        result = await call_gateway(pool, tool_name, arguments)
        if result is not None:
            return result
        # Gateway 失败时 fallback 到旧 MCP
        _logger.warning(f"Gateway 不可用，fallback 到旧 MCP: {tool_name}")
        result = await call_legacy(pool, tool_name, arguments)
        if result is not None:
            return result
        return {"ok": False, "error": f"Gateway 和旧 MCP 均不可用: {tool_name}"}

    return {"ok": False, "error": f"未知路由模式: {mode}"}