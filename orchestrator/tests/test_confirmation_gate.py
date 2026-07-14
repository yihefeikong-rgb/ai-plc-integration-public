import pytest
from unittest.mock import AsyncMock

from orchestrator.core import WorkflowContext
from orchestrator.mcp_client import ToolResult


class ConfirmationRequiredResult:
    allowed = True
    reason = "安全检查通过"
    needs_confirmation = True


class ConfirmationRequiredGate:
    def check_write(self, tag_name, value, *, operator):
        return ConfirmationRequiredResult()


def test_confirmation_required_rejects_write_before_mcp_call():
    context = WorkflowContext(_safety_gate=ConfirmationRequiredGate())

    with pytest.raises(RuntimeError, match="需要人工确认"):
        context._check_safety_gate(
            "plc-mcp-bridge.s7_write",
            {"address": "DB1.MOTOR_RUN", "value": 1},
        )


def test_missing_safety_gate_rejects_write_before_mcp_call():
    context = WorkflowContext(_safety_gate=None)

    with pytest.raises(RuntimeError, match="安全门未配置"):
        context._check_safety_gate(
            "plc-mcp-bridge.s7_write",
            {"address": "DB1.MOTOR_RUN", "value": 1},
        )


@pytest.mark.asyncio
async def test_confirmation_token_reaches_the_final_write_tool_for_consumption():
    pool = type("Pool", (), {
        "call_tool": AsyncMock(return_value=ToolResult.success({"status": "ok"})),
    })()
    context = WorkflowContext(_pool=pool, _safety_gate=ConfirmationRequiredGate())

    result = await context.call_async(
        "plc-mcp-bridge.s7_write",
        address="DB1.MOTOR_RUN",
        value=1,
        confirmation_token="signed-token",
    )

    assert result == {"status": "ok"}
    pool.call_tool.assert_awaited_once_with(
        "plc-mcp-bridge",
        "s7_write",
        {"address": "DB1.MOTOR_RUN", "value": 1, "confirmation_token": "signed-token"},
    )
