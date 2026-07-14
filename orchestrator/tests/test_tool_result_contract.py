"""MCP 工具结果协议：错误不能被工作流误记为 PASS。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mcp.types import CallToolResult, TextContent

from orchestrator.core import OrchestratorEngine, WorkflowContext
from orchestrator.mcp_client import McpClientAdapter, ToolResult
from orchestrator.workflows.nl_to_plcsim_pipeline import (
    register_nl_to_plcsim_pipeline_workflow,
)


def _adapter() -> McpClientAdapter:
    return McpClientAdapter.__new__(McpClientAdapter)


def _text_result(text: str, *, is_error: bool = False) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=text)] if text else [],
        isError=is_error,
    )


def test_structured_success_is_returned_with_an_explicit_success_envelope():
    result = _adapter()._extract_result(
        CallToolResult(content=[], structuredContent={"status": "ok", "value": 42})
    )

    assert isinstance(result, ToolResult)
    assert result.ok is True
    assert result.kind == "success"
    assert result.data == {"status": "ok", "value": 42}


@pytest.mark.parametrize(
    "raw",
    [
        CallToolResult(content=[], structuredContent={"error": True, "message": "项目未打开"}),
        CallToolResult(content=[], structuredContent={"status": "blocked", "reason": "需要人工确认"}),
        _text_result("❌ 编译失败"),
        _text_result("工具执行失败: 项目未打开", is_error=True),
    ],
)
def test_tool_errors_are_never_successful(raw: CallToolResult):
    result = _adapter()._extract_result(raw)

    assert result.ok is False
    assert result.kind == "tool_error"
    assert result.error


def test_unmarked_non_json_text_is_an_invalid_response_not_a_success():
    result = _adapter()._extract_result(_text_result("服务器返回了普通文本"))

    assert result.ok is False
    assert result.kind == "invalid_response"


def test_empty_result_is_an_invalid_response_not_a_success():
    result = _adapter()._extract_result(CallToolResult(content=[]))

    assert result.ok is False
    assert result.kind == "invalid_response"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "kind"),
    [
        (asyncio.TimeoutError(), "timeout"),
        (asyncio.CancelledError(), "cancelled"),
    ],
)
async def test_call_tool_normalizes_timeout_and_cancellation(exception, kind):
    adapter = _adapter()
    adapter._connected = True
    adapter._server = SimpleNamespace(name="test-mcp")
    adapter._session = SimpleNamespace(call_tool=AsyncMock(side_effect=exception))

    result = await adapter.call_tool("test", {})

    assert result.ok is False
    assert result.kind == kind


@pytest.mark.asyncio
async def test_workflow_context_marks_failed_tool_result_as_a_failed_step():
    pool = SimpleNamespace(
        call_tool=AsyncMock(
            return_value=ToolResult.failure("tool_error", "项目未打开")
        )
    )
    ctx = WorkflowContext(_pool=pool)

    with pytest.raises(RuntimeError, match="项目未打开"):
        await ctx.call_async("test-mcp.compile", project="demo")

    assert len(ctx._steps) == 1
    assert ctx._steps[0].ok is False


@pytest.mark.asyncio
async def test_nl_pipeline_stops_on_a_legacy_error_payload_before_next_step():
    engine = OrchestratorEngine()
    register_nl_to_plcsim_pipeline_workflow(engine)
    engine.register_mock(
        "tia-mcp.create_ladder_block",
        lambda **_kwargs: {"error": True, "message": "LAD 生成失败"},
    )

    result = await engine.run_async("nl_to_plcsim_pipeline", input={})

    assert result.ok is False
    assert [step.tool for step in result.steps] == ["tia-mcp.create_ladder_block"]
    assert result.steps[0].ok is False
    assert "LAD 生成失败" in result.error


def test_sync_workflow_error_payload_is_not_reported_as_success():
    engine = OrchestratorEngine()

    @engine.workflow("reported_error")
    def reported_error(_ctx):
        return {"status": "error", "message": "下载未执行"}

    result = engine.run("reported_error")

    assert result.ok is False
    assert "下载未执行" in result.error


@pytest.mark.asyncio
async def test_async_workflow_error_payload_is_not_reported_as_success():
    engine = OrchestratorEngine()

    @engine.workflow("reported_async_error")
    async def reported_async_error(_ctx):
        return {"success": False, "message": "编译未通过"}

    result = await engine.run_async("reported_async_error")

    assert result.ok is False
    assert "编译未通过" in result.error
