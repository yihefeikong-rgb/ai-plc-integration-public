"""
编排层工作流错误路径与边界测试（默认离线套件）。

覆盖：动态工作流、adhoc 执行、结果序列化边界、ToolResult 展开。
"""
from __future__ import annotations

import pytest

from orchestrator.core import (
    OrchestratorEngine,
    WorkflowContext,
    WorkflowResult,
    StepResult,
)
from orchestrator.mcp_client import ToolResult


# ============================================================================
# 动态工作流 CRUD
# ============================================================================

class TestDynamicWorkflows:
    def test_save_and_list(self):
        engine = OrchestratorEngine()
        steps = [{"server": "srv", "tool": "read", "params": {}}]
        engine.save_dynamic_workflow("dyn1", steps)
        items = engine.list_dynamic_workflows()
        assert any(item["name"] == "dyn1" for item in items)

    def test_save_overwrites(self):
        engine = OrchestratorEngine()
        engine.save_dynamic_workflow("dyn1", [{"server": "a", "tool": "x", "params": {}}])
        engine.save_dynamic_workflow("dyn1", [{"server": "b", "tool": "y", "params": {}}])
        steps = engine.get_dynamic_workflow("dyn1")
        assert len(steps) == 1
        assert steps[0]["tool"] == "y"

    def test_get_nonexistent(self):
        engine = OrchestratorEngine()
        assert engine.get_dynamic_workflow("nonexistent") is None

    def test_delete_existing(self):
        engine = OrchestratorEngine()
        engine.save_dynamic_workflow("dyn1", [])
        assert engine.delete_dynamic_workflow("dyn1") is True
        assert engine.get_dynamic_workflow("dyn1") is None

    def test_delete_nonexistent(self):
        engine = OrchestratorEngine()
        assert engine.delete_dynamic_workflow("nonexistent") is False

    def test_dynamic_appears_in_list_workflows(self):
        engine = OrchestratorEngine()
        engine.save_dynamic_workflow("my_dyn", [{"server": "srv", "tool": "t", "params": {}}])
        assert "my_dyn" in engine.list_workflows()

    def test_empty_steps_list(self):
        engine = OrchestratorEngine()
        engine.save_dynamic_workflow("empty_steps", [])
        result = engine.run("empty_steps")
        assert result.ok is True
        assert result.steps == []


# ============================================================================
# Run with stop_on_error
# ============================================================================

class TestStopOnError:
    def test_dynamic_stops_on_first_error_by_default(self):
        engine = OrchestratorEngine()
        engine.register_mock("srv.ok", lambda **kw: {"ok": True})
        engine.register_mock("srv.fail", lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")))

        steps = [
            {"server": "srv", "tool": "ok", "params": {}},
            {"server": "srv", "tool": "fail", "params": {}},
            {"server": "srv", "tool": "ok", "params": {}},
        ]
        engine.save_dynamic_workflow("stop_test", steps)
        result = engine.run("stop_test")
        assert result.ok is False
        assert len(result.steps) == 2  # ok + fail, third not reached

    def test_continue_on_error_when_stop_false(self):
        engine = OrchestratorEngine()
        engine.register_mock("srv.ok", lambda **kw: {"ok": True})
        engine.register_mock("srv.fail", lambda **kw: (_ for _ in ()).throw(ValueError("fail")))

        steps = [
            {"server": "srv", "tool": "ok", "params": {}},
            {"server": "srv", "tool": "fail", "params": {}},
            {"server": "srv", "tool": "ok", "params": {}},
        ]
        engine.save_dynamic_workflow("continue_test", steps)
        result = engine.run("continue_test", stop_on_error=False)
        assert len(result.steps) == 3
        assert result.steps[0].ok is True
        assert result.steps[1].ok is False
        assert result.steps[2].ok is True


# ============================================================================
# Adhoc 工作流
# ============================================================================

class TestAdhocWorkflow:
    @pytest.mark.asyncio
    async def test_run_adhoc_simple(self):
        engine = OrchestratorEngine()
        engine.register_mock("test.echo", lambda message: {"result": message})

        steps = [{"server": "test", "tool": "echo", "params": {"message": "hello"}}]
        result = await engine.run_adhoc(steps)
        assert result.ok is True
        assert len(result.steps) == 1
        assert result.steps[0].data == {"result": "hello"}

    @pytest.mark.asyncio
    async def test_run_adhoc_empty_steps(self):
        engine = OrchestratorEngine()
        result = await engine.run_adhoc([])
        assert result.ok is True
        assert result.steps == []

    @pytest.mark.asyncio
    async def test_run_adhoc_partial_failure(self):
        engine = OrchestratorEngine()
        engine.register_mock("srv.ok", lambda **kw: {"ok": True})
        engine.register_mock("srv.bad", lambda **kw: (_ for _ in ()).throw(RuntimeError("bad")))

        steps = [
            {"server": "srv", "tool": "ok", "params": {}},
            {"server": "srv", "tool": "bad", "params": {}},
        ]
        result = await engine.run_adhoc(steps)
        assert result.ok is False
        assert len(result.steps) == 2
        assert result.steps[0].ok is True
        assert result.steps[1].ok is False

    @pytest.mark.asyncio
    async def test_run_adhoc_continue_on_error(self):
        engine = OrchestratorEngine()
        engine.register_mock("srv.ok", lambda **kw: {"ok": True})
        engine.register_mock("srv.err", lambda **kw: (_ for _ in ()).throw(ValueError("err")))

        steps = [
            {"server": "srv", "tool": "err", "params": {}},
            {"server": "srv", "tool": "ok", "params": {}},
        ]
        result = await engine.run_adhoc(steps, stop_on_error=False)
        assert result.ok is False
        assert len(result.steps) == 2


# ============================================================================
# WorkflowResult / StepResult 序列化边界
# ============================================================================

class TestWorkflowResultEdgeCases:
    def test_all_ok_when_no_steps(self):
        result = WorkflowResult(workflow_name="empty", ok=True, steps=[])
        assert result.ok is True
        assert result.total_duration_ms == 0.0

    def test_failure_with_error_message(self):
        result = WorkflowResult(
            workflow_name="fail",
            ok=False,
            error="something broke",
            total_duration_ms=150.0,
        )
        assert result.ok is False
        assert "broke" in result.error
        assert result.total_duration_ms == 150.0

    def test_step_error_empty(self):
        step = StepResult(tool="x.t", ok=False, error="")
        assert step.ok is False
        assert step.error == ""

    def test_step_duration_float(self):
        step = StepResult(tool="a.b", ok=True, data={"v": 1}, duration_ms=12.3)
        assert isinstance(step.duration_ms, float)


# ============================================================================
# ToolResult 展开边界
# ============================================================================

class TestToolResultUnwrapping:
    def test_ok_result_returns_data(self):
        tr = ToolResult(ok=True, data={"status": "ok"}, kind="tool")
        result = WorkflowContext._unwrap_tool_result(tr)
        assert result == {"status": "ok"}

    def test_fail_result_raises(self):
        tr = ToolResult(ok=False, error="tool crashed", kind="tool")
        with pytest.raises(RuntimeError, match="tool crashed"):
            WorkflowContext._unwrap_tool_result(tr)

    def test_dict_with_error_key_raises(self):
        with pytest.raises(RuntimeError, match="something wrong"):
            WorkflowContext._unwrap_tool_result({"error": "something wrong"})

    def test_dict_with_error_empty_string_passes(self):
        result = WorkflowContext._unwrap_tool_result({"error": "", "data": 1})
        assert result == {"error": "", "data": 1}

    def test_dict_with_ok_false_raises(self):
        with pytest.raises(RuntimeError):
            WorkflowContext._unwrap_tool_result({"ok": False, "message": "nope"})

    def test_dict_with_status_failed_raises(self):
        with pytest.raises(RuntimeError):
            WorkflowContext._unwrap_tool_result({"status": "failed", "message": "gone"})

    def test_dict_with_status_rejected_raises(self):
        with pytest.raises(RuntimeError):
            WorkflowContext._unwrap_tool_result({"status": "rejected"})

    def test_none_raises(self):
        with pytest.raises(RuntimeError, match="返回为空"):
            WorkflowContext._unwrap_tool_result(None)

    def test_empty_string_raises(self):
        with pytest.raises(RuntimeError, match="返回为空"):
            WorkflowContext._unwrap_tool_result("   ")

    def test_string_with_failure_prefix_raises(self):
        with pytest.raises(RuntimeError, match="失败: xxx"):
            WorkflowContext._unwrap_tool_result("失败: xxx")

    def test_string_without_failure_prefix_passes(self):
        result = WorkflowContext._unwrap_tool_result("诊断完成，无错误")
        assert result == "诊断完成，无错误"


# ============================================================================
# 工作流函数返回失败载荷
# ============================================================================

class TestWorkflowReturnsFailurePayload:
    def test_sync_workflow_returns_error_dict(self):
        engine = OrchestratorEngine()

        @engine.workflow("bad_return")
        def bad_return(ctx):
            return {"error": "生成失败", "ok": False}

        result = engine.run("bad_return")
        assert result.ok is False

    def test_async_workflow_returns_error_dict(self):
        engine = OrchestratorEngine()

        @engine.workflow("async_bad")
        async def async_bad(ctx):
            return {"error": "async failed"}

        import asyncio
        result = asyncio.run(engine.run_async("async_bad"))
        assert result.ok is False


# ============================================================================
# 控制工具检测
# ============================================================================

class TestControlToolDetection:
    def test_variable_write_tools_are_control(self):
        ctx = WorkflowContext()
        assert ctx._is_control_tool("plc-mcp-bridge.s7_write") is True
        assert ctx._is_control_tool("opcua-mcp.opcua_write") is True

    def test_engineering_tools_are_control(self):
        ctx = WorkflowContext()
        assert ctx._is_control_tool("plc-mcp-bridge.plc_download_project") is True
        assert ctx._is_control_tool("plc-mcp-bridge.plc_import_block") is True
        assert ctx._is_control_tool("plc-mcp-bridge.plc_delete_db") is True
        assert ctx._is_control_tool("plc-mcp-bridge.plc_compile_project") is True
        assert ctx._is_control_tool("plc-mcp-bridge.plc_apply") is True
        assert ctx._is_control_tool("plc-mcp-bridge.plc_go_online") is True
        assert ctx._is_control_tool("plc-mcp-bridge.plc_go_offline") is True
        assert ctx._is_control_tool("plc-mcp-bridge.plc_archive_project") is True

    def test_readonly_tools_are_not_control(self):
        ctx = WorkflowContext()
        assert ctx._is_control_tool("plc-mcp-bridge.s7_read") is False
        assert ctx._is_control_tool("plc-mcp-bridge.plc_list_blocks") is False
        assert ctx._is_control_tool("plc-mcp-bridge.plc_get_project_info") is False
        assert ctx._is_control_tool("plc-mcp-bridge.plc_search_tags") is False


# ============================================================================
# 已认证操作者
# ============================================================================

class TestAuthenticatedActor:
    def test_actor_from_valid_string(self):
        ctx = WorkflowContext(input={"description": "test"})
        from orchestrator.core import WorkflowExecutionMetadata
        ctx._execution_metadata = WorkflowExecutionMetadata(
            authenticated_operator="local-session:abc123"
        )
        assert ctx._authenticated_actor() == "local-session:abc123"

    def test_empty_actor_when_none(self):
        ctx = WorkflowContext()
        assert ctx._authenticated_actor() == ""

    def test_actor_not_in_input_dict(self):
        from orchestrator.core import WorkflowExecutionMetadata
        ctx = WorkflowContext(
            input={"authenticated_operator": "should_not_be_here"},
            _execution_metadata=WorkflowExecutionMetadata(
                authenticated_operator="real-session:xyz"
            ),
        )
        assert ctx._authenticated_actor() == "real-session:xyz"
