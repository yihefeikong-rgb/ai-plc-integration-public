"""
编排层集成测试 — 使用真实 echo MCP 子进程。

标记为 integration，不在默认离线套件中运行。
直接测试编排引擎 + 真实 MCP 子进程。
"""
from __future__ import annotations

import pytest
import pytest_asyncio

from orchestrator.core import OrchestratorEngine
from orchestrator.mcp_pool import McpConnectionPool
from orchestrator.server_configs import TEST_ECHO


pytestmark = pytest.mark.integration


class TestComplexWorkflowChain:
    """复杂工作流链集成测试（真实 echo MCP 子进程）"""

    @pytest_asyncio.fixture
    async def engine_with_echo(self):
        pool = McpConnectionPool()
        await pool.connect_server(TEST_ECHO)
        engine = OrchestratorEngine()
        engine.set_pool(pool)
        engine.set_safety_gate()
        yield engine
        try:
            await pool.disconnect_all()
        except Exception:
            pass  # FastMCP 3.x 取消域已知问题

    @pytest.mark.asyncio
    async def test_simple_async_echo_workflow(self, engine_with_echo):
        @engine_with_echo.workflow("hello")
        async def hello(ctx):
            result = await ctx.call_async("test-echo.echo", message="hello")
            return {"greeting": result}

        result = await engine_with_echo.run_async("hello")
        assert result.ok is True
        assert len(result.steps) == 1
        assert result.steps[0].data == {"result": "hello"}

    @pytest.mark.asyncio
    async def test_multi_step_data_flow(self, engine_with_echo):
        @engine_with_echo.workflow("chain")
        async def chain(ctx):
            status = await ctx.call_async("test-echo.get_status")
            tools_count = status["tools_count"]
            add_result = await ctx.call_async("test-echo.add", a=tools_count, b=7)
            sum_val = add_result["result"]
            final = await ctx.call_async(
                "test-echo.echo",
                message=f"tools={tools_count} sum={sum_val}",
            )
            return {"final": final}

        result = await engine_with_echo.run_async("chain")
        assert result.ok is True
        assert len(result.steps) == 3
        # tools_count=3, 3+7=10
        assert result.steps[2].data == {"result": "tools=3 sum=10"}

    @pytest.mark.asyncio
    async def test_parallel_workflow_execution(self, engine_with_echo):
        @engine_with_echo.workflow("wf_a")
        async def wf_a(ctx):
            return await ctx.call_async("test-echo.add", a=1, b=2)

        @engine_with_echo.workflow("wf_b")
        async def wf_b(ctx):
            return await ctx.call_async("test-echo.add", a=10, b=20)

        r1 = await engine_with_echo.run_async("wf_a")
        r2 = await engine_with_echo.run_async("wf_b")

        assert r1.ok and r2.ok
        assert r1.steps[0].data == {"result": 3}
        assert r2.steps[0].data == {"result": 30}

    @pytest.mark.asyncio
    async def test_workflow_with_input_parameters(self, engine_with_echo):
        @engine_with_echo.workflow("param_test")
        async def param_test(ctx):
            a = ctx.input.get("a", 0)
            b = ctx.input.get("b", 0)
            return await ctx.call_async("test-echo.add", a=a, b=b)

        result = await engine_with_echo.run_async(
            "param_test", input={"a": 100, "b": 200},
        )
        assert result.ok is True
        assert result.steps[0].data == {"result": 300}

    @pytest.mark.asyncio
    async def test_nonexistent_tool_returns_failure(self, engine_with_echo):
        """调用不存在的 MCP 工具时工作流失败关闭（fail-closed）"""

        @engine_with_echo.workflow("bad_tool_wf")
        async def bad_tool_wf(ctx):
            return await ctx.call_async("test-echo.nonexistent")

        result = await engine_with_echo.run_async("bad_tool_wf")
        # MCP 的 error 响应被 _unwrap_tool_result 转为 RuntimeError
        # 导致工作流失败关闭，这是 fail-closed 的正确行为
        assert result.ok is False
        assert result.steps[0].ok is False

    @pytest.mark.asyncio
    async def test_many_small_add_calls(self, engine_with_echo):
        """多次 add 调用验证稳定性"""

        @engine_with_echo.workflow("sum20")
        async def sum20(ctx):
            total = 0
            for i in range(20):
                r = await ctx.call_async("test-echo.add", a=total, b=i)
                total = r["result"]
            return {"sum": total}

        result = await engine_with_echo.run_async("sum20")
        assert result.ok is True
        assert len(result.steps) == 20
        # 0+0+1+2+...+19 = 190
        assert result.steps[-1].data == {"result": 190}
