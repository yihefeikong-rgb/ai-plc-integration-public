"""
编排层集成测试 — 验证真实 MCP 服务器连接。

使用 test_echo_server.py 作为最小测试服务器，
验证编排层的完整工作流：连接 → 发现 → 调用 → 断开。
"""

import pytest
import pytest_asyncio
import asyncio
from pathlib import Path

from orchestrator.core import OrchestratorEngine, WorkflowContext
from orchestrator.mcp_pool import McpConnectionPool
from orchestrator.mcp_client import McpClientAdapter
from orchestrator.registry import ServerInfo, ToolInfo


# 测试服务器配置
ECHO_SERVER = ServerInfo(
    name="test-echo",
    description="集成测试用最小 MCP 服务器",
    command=str(Path(r"D:\Python3\python.exe")),
    args=[str(Path(__file__).parent / "test_echo_server.py")],
    cwd=str(Path(__file__).parent.parent.parent),
)


class TestMcpClientIntegration:
    """MCP 客户端适配器集成测试（需要真实启动子进程）"""

    @pytest_asyncio.fixture
    async def adapter(self):
        """创建并连接 MCP 适配器"""
        adapter = McpClientAdapter(ECHO_SERVER)
        await adapter.connect()
        yield adapter
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_connect_and_list_tools(self, adapter):
        """验证连接和工具发现"""
        tools = await adapter.list_tools()
        assert len(tools) == 3
        tool_names = {t.name for t in tools}
        assert tool_names == {"echo", "add", "get_status"}

    @pytest.mark.asyncio
    async def test_call_echo(self, adapter):
        """验证 echo 工具调用"""
        result = await adapter.call_tool("echo", {"message": "hello integration"})
        assert result == {"result": "hello integration"}

    @pytest.mark.asyncio
    async def test_call_add(self, adapter):
        """验证 add 工具调用"""
        result = await adapter.call_tool("add", {"a": 42, "b": 58})
        assert result == {"result": 100}

    @pytest.mark.asyncio
    async def test_call_get_status(self, adapter):
        """验证 get_status 工具调用"""
        result = await adapter.call_tool("get_status", {})
        assert result["status"] == "ok"
        assert result["server"] == "test-echo"
        assert result["tools_count"] == 3


class TestMcpPoolIntegration:
    """MCP 连接池集成测试"""

    @pytest_asyncio.fixture
    async def pool(self):
        """创建并连接连接池"""
        pool = McpConnectionPool()
        await pool.connect_server(ECHO_SERVER)
        yield pool
        await pool.disconnect_all()

    @pytest.mark.asyncio
    async def test_pool_connect(self, pool):
        """验证连接池状态"""
        assert pool.connected_count == 1
        assert "test-echo" in pool.server_names

    @pytest.mark.asyncio
    async def test_pool_call_tool(self, pool):
        """验证通过连接池调用工具"""
        result = await pool.call_tool("test-echo", "echo", {"message": "pool test"})
        assert result == {"result": "pool test"}

    @pytest.mark.asyncio
    async def test_pool_get_adapter(self, pool):
        """验证获取适配器"""
        adapter = pool.get_adapter("test-echo")
        assert adapter is not None
        assert adapter.server_name == "test-echo"

    @pytest.mark.asyncio
    async def test_pool_get_nonexistent_adapter(self, pool):
        """验证获取不存在的适配器返回 None"""
        adapter = pool.get_adapter("nonexistent")
        assert adapter is None


class TestWorkflowIntegration:
    """工作流端到端集成测试"""

    @pytest_asyncio.fixture
    async def engine_with_pool(self):
        """创建带连接池的编排引擎"""
        engine = OrchestratorEngine()
        pool = McpConnectionPool()
        await pool.connect_server(ECHO_SERVER)
        engine.set_pool(pool)
        yield engine
        await pool.disconnect_all()

    @pytest.mark.asyncio
    async def test_async_workflow(self, engine_with_pool):
        """验证异步工作流端到端执行"""
        @engine_with_pool.workflow("integration_test")
        async def integration_test(ctx):
            echo = await ctx.call_async("test-echo.echo", message="workflow integration")
            add = await ctx.call_async("test-echo.add", a=10, b=20)
            status = await ctx.call_async("test-echo.get_status")
            return {"echo": echo, "add": add, "status": status}

        result = await engine_with_pool.run_async("integration_test")

        assert result.ok is True
        assert len(result.steps) == 3
        assert result.error == ""

        # 验证各步骤结果
        assert result.steps[0].tool == "test-echo.echo"
        assert result.steps[0].ok is True
        assert result.steps[0].data == {"result": "workflow integration"}

        assert result.steps[1].tool == "test-echo.add"
        assert result.steps[1].ok is True
        assert result.steps[1].data == {"result": 30}

        assert result.steps[2].tool == "test-echo.get_status"
        assert result.steps[2].ok is True
        assert result.steps[2].data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_workflow_with_error(self, engine_with_pool):
        """验证工作流中工具调用失败的处理"""
        @engine_with_pool.workflow("error_test")
        async def error_test(ctx):
            # 调用不存在的工具 — MCP 返回错误响应（不抛异常）
            result = await ctx.call_async("test-echo.nonexistent")
            # MCP 协议返回 {'error': True, 'message': '...'}
            # 继续调用存在的工具
            echo = await ctx.call_async("test-echo.echo", message="after error")
            return {"error_result": result, "echo": echo}

        result = await engine_with_pool.run_async("error_test")

        # 两步都执行成功（MCP 层面不抛异常）
        assert len(result.steps) == 2
        assert result.steps[0].ok is True  # MCP 返回了错误响应但不抛异常
        assert result.steps[0].data.get("error") is True  # 错误标记
        assert result.steps[1].ok is True
        assert result.steps[1].data == {"result": "after error"}

    @pytest.mark.asyncio
    async def test_multi_step_data_flow(self, engine_with_pool):
        """验证工作流中步骤间数据传递"""
        @engine_with_pool.workflow("data_flow_test")
        async def data_flow_test(ctx):
            # 步骤 1: 获取状态
            status = await ctx.call_async("test-echo.get_status")
            tools_count = status["tools_count"]

            # 步骤 2: 使用步骤 1 的结果
            add = await ctx.call_async("test-echo.add", a=tools_count, b=7)
            result_value = add["result"]

            # 步骤 3: 组合结果
            echo = await ctx.call_async(
                "test-echo.echo",
                message=f"count={tools_count}, sum={result_value}",
            )

            return echo

        result = await engine_with_pool.run_async("data_flow_test")

        assert result.ok is True
        # tools_count=3, 3+7=10
        assert result.steps[2].data == {"result": "count=3, sum=10"}
