"""
测试 orchestrator.registry — 服务器/工具注册表。
"""
import pytest
from orchestrator.registry import (
    Registry,
    ToolInfo,
    ServerInfo,
    get_registry,
)


class TestToolInfo:
    """ToolInfo 数据类"""

    def test_create_tool(self):
        tool = ToolInfo(name="compile_project", description="编译 TIA 项目")
        assert tool.name == "compile_project"
        assert tool.server == ""

    def test_tool_with_server(self):
        tool = ToolInfo(
            name="compile_project",
            description="编译 TIA 项目",
            server="tia-mcp",
        )
        assert tool.server == "tia-mcp"


class TestServerInfo:
    """ServerInfo 数据类"""

    def test_create_server(self):
        server = ServerInfo(name="tia-mcp", description="TIA Portal MCP 服务器")
        assert server.name == "tia-mcp"
        assert server.protocol == "stdio"
        assert server.tools == []

    def test_server_with_tools(self):
        tool = ToolInfo(name="compile_project")
        server = ServerInfo(
            name="tia-mcp",
            tools=[tool],
        )
        assert len(server.tools) == 1
        assert server.tools[0].name == "compile_project"


class TestRegistry:
    """Registry 注册表"""

    def test_register_server(self):
        reg = Registry()
        server = ServerInfo(
            name="tia-mcp",
            tools=[
                ToolInfo(name="compile_project"),
                ToolInfo(name="download_to_plcsim"),
            ],
        )
        reg.register_server(server)
        assert reg.server_count() == 1
        assert reg.tool_count() == 2

    def test_register_server_auto_sets_tool_server(self):
        reg = Registry()
        server = ServerInfo(
            name="tia-mcp",
            tools=[ToolInfo(name="compile_project")],
        )
        reg.register_server(server)
        tool = reg.get_tool("tia-mcp.compile_project")
        assert tool is not None
        assert tool.server == "tia-mcp"

    def test_register_tool_individually(self):
        reg = Registry()
        reg.register_server(ServerInfo(name="tia-mcp"))
        reg.register_tool("tia-mcp", ToolInfo(name="compile_project"))
        assert reg.tool_count() == 1
        assert reg.get_tool("tia-mcp.compile_project") is not None

    def test_get_tool_not_found(self):
        reg = Registry()
        assert reg.get_tool("nonexistent.tool") is None

    def test_get_server_not_found(self):
        reg = Registry()
        assert reg.get_server("nonexistent") is None

    def test_list_servers(self):
        reg = Registry()
        reg.register_server(ServerInfo(name="tia-mcp"))
        reg.register_server(ServerInfo(name="plc-mcp-bridge"))
        assert reg.list_servers() == ["tia-mcp", "plc-mcp-bridge"]

    def test_list_tools_all(self):
        reg = Registry()
        reg.register_server(
            ServerInfo(
                name="tia-mcp",
                tools=[ToolInfo(name="tool_a"), ToolInfo(name="tool_b")],
            )
        )
        reg.register_server(
            ServerInfo(
                name="plc-mcp-bridge",
                tools=[ToolInfo(name="tool_c")],
            )
        )
        tools = reg.list_tools()
        assert len(tools) == 3

    def test_list_tools_filtered(self):
        reg = Registry()
        reg.register_server(
            ServerInfo(
                name="tia-mcp",
                tools=[ToolInfo(name="tool_a"), ToolInfo(name="tool_b")],
            )
        )
        tools = reg.list_tools(server_name="tia-mcp")
        assert len(tools) == 2

    def test_list_tools_filtered_empty(self):
        reg = Registry()
        tools = reg.list_tools(server_name="nonexistent")
        assert tools == []

    def test_tool_count_empty(self):
        reg = Registry()
        assert reg.tool_count() == 0
        assert reg.server_count() == 0

    def test_get_registry_singleton(self):
        reg1 = get_registry()
        reg2 = get_registry()
        assert reg1 is reg2

    def test_register_duplicate_server_overwrites(self):
        reg = Registry()
        reg.register_server(ServerInfo(name="tia-mcp", tools=[ToolInfo(name="t1")]))
        reg.register_server(ServerInfo(name="tia-mcp", tools=[ToolInfo(name="t2")]))
        # 第二次注册覆盖
        assert reg.tool_count() == 1
        assert reg.get_tool("tia-mcp.t2") is not None

    def test_register_tool_to_unregistered_server(self):
        reg = Registry()
        reg.register_tool("my-server", ToolInfo(name="my_tool"))
        assert reg.tool_count() == 1
        assert reg.get_tool("my-server.my_tool") is not None
        # 服务器未注册
        assert reg.get_server("my-server") is None


# ============================================================================
# OrchestratorEngine 和 WorkflowContext 测试
# ============================================================================

from orchestrator.core import (
    OrchestratorEngine,
    WorkflowContext,
    WorkflowResult,
    StepResult,
)


class TestWorkflowContext:
    """WorkflowContext 上下文"""

    def test_create_context(self):
        ctx = WorkflowContext(input={"prompt": "hello"})
        assert ctx.input["prompt"] == "hello"
        assert ctx._steps == []

    def test_call_mock_tool(self):
        ctx = WorkflowContext(
            _mock_tools={"test.tool": lambda x: {"result": x * 2}}
        )
        result = ctx.call("test.tool", x=21)
        assert result == {"result": 42}

    def test_call_mock_tool_records_step(self):
        ctx = WorkflowContext(
            _mock_tools={"test.tool": lambda x: {"result": x}}
        )
        ctx.call("test.tool", x=1)
        assert len(ctx._steps) == 1
        step = ctx._steps[0]
        assert step.tool == "test.tool"
        assert step.ok is True
        assert step.duration_ms >= 0

    def test_call_unregistered_tool_raises(self):
        ctx = WorkflowContext()
        with pytest.raises(RuntimeError, match="没有 mock 实现"):
            ctx.call("nonexistent.tool")

    def test_call_tool_records_error_step(self):
        def failing_tool(**kwargs):
            raise ValueError("something went wrong")

        ctx = WorkflowContext(_mock_tools={"bad.tool": failing_tool})
        with pytest.raises(ValueError, match="something went wrong"):
            ctx.call("bad.tool")
        assert len(ctx._steps) == 1
        step = ctx._steps[0]
        assert step.ok is False
        assert "something went wrong" in step.error


class TestOrchestratorEngine:
    """OrchestratorEngine 编排引擎"""

    def test_register_workflow(self):
        engine = OrchestratorEngine()

        @engine.workflow("my_wf")
        def my_wf(ctx):
            return {"status": "ok"}

        assert "my_wf" in engine.list_workflows()
        assert engine.get_workflow("my_wf") is not None

    def test_list_workflows_empty(self):
        engine = OrchestratorEngine()
        assert engine.list_workflows() == []

    def test_run_simple_workflow(self):
        engine = OrchestratorEngine()

        @engine.workflow("simple")
        def simple(ctx):
            step1 = ctx.call("mcp.tool_a", x=1)
            return {"done": True, "data": step1}

        engine.register_mock("mcp.tool_a", lambda x: {"result": x * 10})

        result = engine.run("simple")
        assert result.ok is True
        assert result.workflow_name == "simple"
        assert len(result.steps) == 1
        assert result.steps[0].tool == "mcp.tool_a"

    def test_run_workflow_not_found(self):
        engine = OrchestratorEngine()
        result = engine.run("nonexistent")
        assert result.ok is False
        assert "未找到工作流" in result.error

    def test_run_workflow_with_input(self):
        engine = OrchestratorEngine()

        @engine.workflow("with_input")
        def with_input_wf(ctx):
            name = ctx.input.get("name", "unknown")
            return {"greeting": f"hello {name}"}

        result = engine.run("with_input", input={"name": "world"})
        assert result.ok is True

    def test_run_workflow_with_error(self):
        engine = OrchestratorEngine()

        @engine.workflow("failing")
        def failing_wf(ctx):
            raise ValueError("boom")

        result = engine.run("failing")
        assert result.ok is False
        assert "boom" in result.error

    def test_run_workflow_partial_failure(self):
        engine = OrchestratorEngine()

        @engine.workflow("partial")
        def partial_wf(ctx):
            ctx.call("mcp.good", x=1)
            ctx.call("mcp.bad", x=2)
            ctx.call("mcp.never_reached", x=3)

        def bad_tool(**kwargs):
            raise RuntimeError("tool failed")

        engine.register_mock("mcp.good", lambda x: {"ok": True})
        engine.register_mock("mcp.bad", bad_tool)
        engine.register_mock("mcp.never_reached", lambda x: {"ok": True})

        result = engine.run("partial")
        assert result.ok is False
        assert len(result.steps) == 2  # good + bad，never_reached 未执行
        assert result.steps[0].ok is True
        assert result.steps[1].ok is False

    def test_register_mocks_batch(self):
        engine = OrchestratorEngine()
        engine.register_mocks({
            "mcp.a": lambda x: {"a": x},
            "mcp.b": lambda x: {"b": x},
        })
        assert len(engine._mock_tools) == 2

    def test_run_multi_step_workflow(self):
        engine = OrchestratorEngine()

        @engine.workflow("multi_step")
        def multi_step(ctx):
            s1 = ctx.call("tia.generate", prompt=ctx.input.get("prompt"))
            s2 = ctx.call("tia.import_scl", scl_path=s1["scl_path"])
            s3 = ctx.call("tia.compile", project_path=s2["project_path"])
            return {"status": "ok", "scl_path": s1["scl_path"]}

        engine.register_mocks({
            "tia.generate": lambda prompt: {"scl_path": "/tmp/fb.scl"},
            "tia.import_scl": lambda scl_path: {"project_path": "/tmp/proj"},
            "tia.compile": lambda project_path: {"ok": True},
        })

        result = engine.run("multi_step", input={"prompt": "生成电机FB"})
        assert result.ok is True
        assert len(result.steps) == 3
        assert result.steps[0].tool == "tia.generate"
        assert result.steps[1].tool == "tia.import_scl"
        assert result.steps[2].tool == "tia.compile"

    def test_run_with_custom_context(self):
        engine = OrchestratorEngine()

        @engine.workflow("custom_ctx")
        def custom_ctx_wf(ctx):
            ctx.call("mcp.tool", val=ctx.input["val"])
            return {"done": True}

        engine.register_mock("mcp.tool", lambda val: {"val": val})

        ctx = WorkflowContext(
            input={"val": 42},
            _mock_tools=engine._mock_tools,
        )
        result = engine.run("custom_ctx", context=ctx)
        assert result.ok is True

    def test_workflow_decorator_preserves_function(self):
        engine = OrchestratorEngine()

        @engine.workflow("decorated")
        def decorated(ctx):
            return {"result": 42}

        # 装饰器返回原始函数
        assert decorated.__name__ == "decorated"
        result = engine.run("decorated")
        assert result.ok is True


class TestStepResult:
    """StepResult 数据类"""

    def test_success_step(self):
        step = StepResult(tool="mcp.tool", ok=True, data={"v": 1})
        assert step.ok is True
        assert step.data == {"v": 1}

    def test_error_step(self):
        step = StepResult(tool="mcp.tool", ok=False, error="bad")
        assert step.ok is False
        assert step.error == "bad"


class TestWorkflowResult:
    """WorkflowResult 数据类"""

    def test_success_result(self):
        result = WorkflowResult(workflow_name="wf", ok=True)
        assert result.ok is True
        assert result.steps == []

    def test_failure_result(self):
        result = WorkflowResult(workflow_name="wf", ok=False, error="fail")
        assert result.ok is False
        assert result.error == "fail"