from __future__ import annotations

import pytest

from orchestrator.core import WorkflowContext
from orchestrator.gateway_router import compare_results, route_tia_read
from orchestrator.mcp_client import ToolResult


class FakePool:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def call_tool(self, server, tool, arguments):
        self.calls.append((server, tool, arguments))
        response = self.responses[(server, tool)]
        if isinstance(response, Exception):
            raise response
        return response


def _blocks(*names):
    return {
        "ok": True,
        "result": {
            "blocks": [
                {"name": name, "type": "FB", "number": "1", "language": "LAD"}
                for name in names
            ]
        },
    }


@pytest.mark.asyncio
async def test_shadow_calls_both_and_returns_legacy_result():
    legacy = _blocks("FB1")
    pool = FakePool({
        ("plc-gateway", "tia.block.list"): _blocks("FB1"),
        ("tia-mcp", "list_blocks"): legacy,
    })

    result = await route_tia_read(pool, "tia.block.list", {"block_type": "all"})

    assert result is legacy
    assert {call[:2] for call in pool.calls} == {
        ("plc-gateway", "tia.block.list"),
        ("tia-mcp", "list_blocks"),
    }


@pytest.mark.asyncio
async def test_shadow_keeps_legacy_when_gateway_fails():
    legacy = _blocks("FB1")
    pool = FakePool({
        ("plc-gateway", "tia.block.list"): RuntimeError("gateway down"),
        ("tia-mcp", "list_blocks"): legacy,
    })

    assert await route_tia_read(pool, "tia.block.list") is legacy


@pytest.mark.asyncio
async def test_shadow_never_uses_gateway_as_legacy_fallback():
    pool = FakePool({
        ("plc-gateway", "tia.block.list"): _blocks("FB1"),
        ("tia-mcp", "list_blocks"): RuntimeError("legacy down"),
    })

    result = await route_tia_read(pool, "tia.block.list")

    assert result["ok"] is False
    assert result["gateway_diagnostics"]["available"] is True


@pytest.mark.asyncio
async def test_shadow_normalizes_real_tool_results_before_comparison():
    legacy = ToolResult.success(_blocks("FB1"))
    pool = FakePool({
        ("plc-gateway", "tia.block.list"): ToolResult.success(_blocks("FB1")),
        ("tia-mcp", "list_blocks"): legacy,
    })

    result = await route_tia_read(pool, "tia.block.list")

    assert result == _blocks("FB1")


@pytest.mark.asyncio
async def test_failed_tool_result_is_not_treated_as_success():
    pool = FakePool({
        ("plc-gateway", "tia.block.list"): ToolResult.failure("transport", "gateway down"),
        ("tia-mcp", "list_blocks"): ToolResult.failure("transport", "legacy down"),
    })

    result = await route_tia_read(pool, "tia.block.list")

    assert result["ok"] is False
    assert result["gateway_diagnostics"]["available"] is False


def test_block_comparison_ignores_order_and_reports_missing_blocks():
    comparison = compare_results("tia.block.list", _blocks("FB1"), _blocks("FB2", "FB1"))

    assert comparison["semantic_match"] is False
    assert comparison["differences"]["missing_in_gateway"] == ["FB2"]


@pytest.mark.asyncio
async def test_workflow_context_routes_the_real_legacy_block_list_call(monkeypatch):
    monkeypatch.setenv("PLC_GATEWAY_MODE", "shadow")
    legacy = _blocks("FB1")
    pool = FakePool({
        ("plc-gateway", "tia.block.list"): _blocks("FB1"),
        ("tia-mcp", "list_blocks"): legacy,
    })
    context = WorkflowContext(_pool=pool)

    assert await context.call_async("tia-mcp.list_blocks") is legacy
    assert len(pool.calls) == 2
