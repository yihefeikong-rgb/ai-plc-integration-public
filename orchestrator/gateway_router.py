"""Gateway 与旧 TIA MCP 的受控只读影子路由。"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

_logger = logging.getLogger(__name__)

READ_ROUTE_MAP = {
    "tia.block.list": {
        "gateway": ("plc-gateway", "tia.block.list"),
        "legacy": ("tia-mcp", "list_blocks"),
    },
}


def is_tia_read_operation(operation: str) -> bool:
    return operation in READ_ROUTE_MAP


async def _call(pool, endpoint: tuple[str, str], arguments: dict[str, Any]) -> tuple[dict | None, str]:
    try:
        return await pool.call_tool(*endpoint, arguments), ""
    except Exception as exc:
        _logger.warning("只读影子调用失败: %s.%s: %s", endpoint[0], endpoint[1], exc)
        return None, str(exc)


def _block_set(result: dict | None) -> set[tuple[str, str, str, str]]:
    if not isinstance(result, dict):
        return set()
    data = result.get("result", result)
    blocks = data.get("blocks", data.get("Blocks", [])) if isinstance(data, dict) else data
    if not isinstance(blocks, list):
        return set()
    normalized = set()
    for block in blocks:
        if not isinstance(block, dict):
            normalized.add((str(block), "", "", ""))
            continue
        normalized.add((
            str(block.get("name", block.get("Name", ""))),
            str(block.get("type", block.get("BlockType", ""))),
            str(block.get("number", block.get("Number", ""))),
            str(block.get("language", block.get("Language", ""))),
        ))
    return normalized


def compare_results(operation: str, gateway_result: dict | None, legacy_result: dict | None) -> dict:
    """比较标准化只读结果；不记录项目路径、完整 XML 或原始载荷。"""
    gateway_ok = bool(gateway_result and gateway_result.get("ok") is True)
    legacy_ok = bool(legacy_result and legacy_result.get("ok", True) is not False)
    comparison: dict[str, Any] = {
        "operation": operation,
        "gateway_ok": gateway_ok,
        "legacy_ok": legacy_ok,
        "semantic_match": False,
        "differences": {"missing_in_gateway": [], "extra_in_gateway": [], "field_mismatches": []},
    }
    if not (gateway_ok and legacy_ok):
        return comparison
    gateway_blocks = _block_set(gateway_result)
    legacy_blocks = _block_set(legacy_result)
    comparison["differences"]["missing_in_gateway"] = sorted(item[0] for item in legacy_blocks - gateway_blocks)
    comparison["differences"]["extra_in_gateway"] = sorted(item[0] for item in gateway_blocks - legacy_blocks)
    comparison["semantic_match"] = gateway_blocks == legacy_blocks
    return comparison


async def route_tia_read(pool, canonical_operation: str, arguments: dict[str, Any] | None = None,
                         mode: str = "shadow") -> dict:
    """路由已登记只读操作；影子模式始终返回旧 MCP 结果。"""
    route = READ_ROUTE_MAP.get(canonical_operation)
    if route is None:
        return {"ok": False, "status": "blocked", "error": f"未登记的 Gateway 只读操作: {canonical_operation}"}
    args = arguments or {}
    if mode == "off":
        result, error = await _call(pool, route["legacy"], args)
        return result or {"ok": False, "status": "error", "error": f"旧 MCP 不可用: {error}"}
    if mode == "primary":
        if os.environ.get("PLC_GATEWAY_PRIMARY_ACK") != "I_UNDERSTAND_READ_MIGRATION":
            return {"ok": False, "status": "blocked", "error": "Primary 只读迁移尚未确认"}
        result, error = await _call(pool, route["gateway"], args)
        return result or {"ok": False, "status": "error", "error": f"Gateway 不可用: {error}"}
    if mode != "shadow":
        return {"ok": False, "status": "blocked", "error": f"未知 Gateway 路由模式: {mode}"}

    gateway_task = _call(pool, route["gateway"], args)
    legacy_task = _call(pool, route["legacy"], args)
    (gateway_result, gateway_error), (legacy_result, legacy_error) = await asyncio.gather(gateway_task, legacy_task)
    comparison = compare_results(canonical_operation, gateway_result, legacy_result)
    _logger.info(
        "Gateway 影子比较 operation=%s gateway_ok=%s legacy_ok=%s semantic_match=%s differences=%d",
        canonical_operation, comparison["gateway_ok"], comparison["legacy_ok"], comparison["semantic_match"],
        sum(len(value) for value in comparison["differences"].values()),
    )
    if legacy_result is not None:
        return legacy_result
    return {
        "ok": False,
        "status": "error",
        "error": f"旧 MCP 不可用: {legacy_error}",
        "gateway_diagnostics": {"available": gateway_result is not None, "error": gateway_error},
    }
