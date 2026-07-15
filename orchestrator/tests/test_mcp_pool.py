"""
测试 orchestrator.mcp_pool — MCP 连接池。
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from orchestrator.registry import ServerInfo
from orchestrator.mcp_pool import McpConnectionPool


# ============================================================================
# 辅助函数
# ============================================================================

def _make_server_info(name: str) -> ServerInfo:
    return ServerInfo(
        name=name,
        description=f"测试服务器 {name}",
        command="python",
        args=["server.py"],
        cwd="/fake/path",
    )


def _make_mock_adapter():
    """创建 mock McpClientAdapter"""
    adapter = AsyncMock()
    adapter.server_name = "mock-server"
    adapter.is_connected = True
    adapter.connect = AsyncMock()
    adapter.disconnect = AsyncMock()
    adapter.call_tool = AsyncMock(return_value={"result": "ok"})
    adapter.list_tools = AsyncMock(return_value=[])
    return adapter


# ============================================================================
# McpConnectionPool 测试
# ============================================================================

class TestMcpConnectionPool:
    """McpConnectionPool 单元测试"""

    def test_create_pool(self):
        pool = McpConnectionPool()
        assert pool.server_names == []
        assert pool.connected_count == 0

    @pytest.mark.asyncio
    async def test_connect_server(self):
        """测试连接服务器"""
        pool = McpConnectionPool()
        adapter = _make_mock_adapter()

        with patch(
            "orchestrator.mcp_pool.McpClientAdapter",
            return_value=adapter,
        ):
            await pool.connect_server(_make_server_info("srv-a"))

            assert pool.connected_count == 1
            assert "srv-a" in pool.server_names
            adapter.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_multiple_servers(self):
        """测试连接多个服务器"""
        pool = McpConnectionPool()
        adapter1 = _make_mock_adapter()
        adapter2 = _make_mock_adapter()

        with patch(
            "orchestrator.mcp_pool.McpClientAdapter",
            side_effect=[adapter1, adapter2],
        ):
            await pool.connect_server(_make_server_info("srv-a"))
            await pool.connect_server(_make_server_info("srv-b"))

            assert pool.connected_count == 2
            assert set(pool.server_names) == {"srv-a", "srv-b"}

    @pytest.mark.asyncio
    async def test_connect_duplicate_server_skips(self):
        """重复连接同名服务器应跳过"""
        pool = McpConnectionPool()
        adapter = _make_mock_adapter()

        with patch(
            "orchestrator.mcp_pool.McpClientAdapter",
            return_value=adapter,
        ):
            await pool.connect_server(_make_server_info("srv-a"))
            await pool.connect_server(_make_server_info("srv-a"))

            assert pool.connected_count == 1
            # connect 只应调用一次
            adapter.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_call_tool(self):
        """测试通过连接池调用工具"""
        pool = McpConnectionPool()
        adapter = _make_mock_adapter()

        with patch(
            "orchestrator.mcp_pool.McpClientAdapter",
            return_value=adapter,
        ):
            await pool.connect_server(_make_server_info("srv-a"))
            result = await pool.call_tool("srv-a", "read_tag", {"tag": "DB1.x"})

            assert result == {"result": "ok"}
            adapter.call_tool.assert_awaited_once_with(
                "read_tag", {"tag": "DB1.x"}
            )

    @pytest.mark.asyncio
    async def test_call_tool_server_not_found(self):
        """调用未连接服务器的工具应报错"""
        pool = McpConnectionPool()
        with pytest.raises(RuntimeError, match="未在连接池中"):
            await pool.call_tool("nonexistent", "tool", {})

    @pytest.mark.asyncio
    async def test_call_tool_with_no_args(self):
        """测试无参数工具调用"""
        pool = McpConnectionPool()
        adapter = _make_mock_adapter()

        with patch(
            "orchestrator.mcp_pool.McpClientAdapter",
            return_value=adapter,
        ):
            await pool.connect_server(_make_server_info("srv-a"))
            result = await pool.call_tool("srv-a", "ping")

            assert result == {"result": "ok"}
            adapter.call_tool.assert_awaited_once_with("ping", None)

    @pytest.mark.asyncio
    async def test_get_adapter(self):
        """测试获取单个适配器"""
        pool = McpConnectionPool()
        adapter = _make_mock_adapter()

        with patch(
            "orchestrator.mcp_pool.McpClientAdapter",
            return_value=adapter,
        ):
            await pool.connect_server(_make_server_info("srv-a"))
            retrieved = pool.get_adapter("srv-a")

            assert retrieved is adapter

        assert pool.get_adapter("nonexistent") is None

    @pytest.mark.asyncio
    async def test_disconnect_server(self):
        """测试断开单个服务器"""
        pool = McpConnectionPool()
        adapter = _make_mock_adapter()

        with patch(
            "orchestrator.mcp_pool.McpClientAdapter",
            return_value=adapter,
        ):
            await pool.connect_server(_make_server_info("srv-a"))
            await pool.disconnect_server("srv-a")

            assert pool.connected_count == 0
            adapter.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "disconnect_operation",
        ["disconnect_server", "disconnect_all"],
    )
    async def test_connect_waits_for_in_progress_disconnect(
        self,
        disconnect_operation,
    ):
        """旧适配器退出完成前，不得启动同名新适配器。"""
        pool = McpConnectionPool()
        server_info = _make_server_info("srv-a")
        old_adapter = _make_mock_adapter()
        new_adapter = _make_mock_adapter()
        old_disconnect_started = asyncio.Event()
        release_old_disconnect = asyncio.Event()
        old_disconnect_finished = asyncio.Event()
        new_connect_started = asyncio.Event()

        async def block_old_disconnect():
            old_disconnect_started.set()
            await release_old_disconnect.wait()
            old_disconnect_finished.set()

        async def record_new_connect():
            new_connect_started.set()

        old_adapter.disconnect.side_effect = block_old_disconnect
        new_adapter.connect.side_effect = record_new_connect

        disconnect_task = None
        connect_task = None
        observations = {}
        results = []
        with patch(
            "orchestrator.mcp_pool.McpClientAdapter",
            side_effect=[old_adapter, new_adapter],
        ):
            await pool.connect_server(server_info)
            if disconnect_operation == "disconnect_server":
                disconnect_task = asyncio.create_task(
                    pool.disconnect_server(server_info.name)
                )
            else:
                disconnect_task = asyncio.create_task(pool.disconnect_all())

            try:
                await asyncio.wait_for(old_disconnect_started.wait(), timeout=1)
                connect_task = asyncio.create_task(pool.connect_server(server_info))
                await asyncio.sleep(0)
                observations = {
                    "connect_completed_before_release": connect_task.done(),
                    "new_connect_started_before_release": (
                        new_connect_started.is_set()
                    ),
                }
                release_old_disconnect.set()
                results = await asyncio.gather(
                    disconnect_task,
                    connect_task,
                    return_exceptions=True,
                )
            finally:
                release_old_disconnect.set()
                pending = [
                    task
                    for task in (disconnect_task, connect_task)
                    if task is not None and not task.done()
                ]
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)

        assert results == [None, None]
        assert {
            **observations,
            "old_disconnect_finished": old_disconnect_finished.is_set(),
            "new_connect_started": new_connect_started.is_set(),
            "pool_uses_new_adapter": (
                pool.get_adapter(server_info.name) is new_adapter
            ),
        } == {
            "connect_completed_before_release": False,
            "new_connect_started_before_release": False,
            "old_disconnect_finished": True,
            "new_connect_started": True,
            "pool_uses_new_adapter": True,
        }

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_server(self):
        """断开不存在的服务器不应报错"""
        pool = McpConnectionPool()
        await pool.disconnect_server("nonexistent")  # 不应抛出异常

    @pytest.mark.asyncio
    async def test_disconnect_all(self):
        """测试断开所有连接"""
        pool = McpConnectionPool()
        adapter1 = _make_mock_adapter()
        adapter2 = _make_mock_adapter()

        with patch(
            "orchestrator.mcp_pool.McpClientAdapter",
            side_effect=[adapter1, adapter2],
        ):
            await pool.connect_server(_make_server_info("srv-a"))
            await pool.connect_server(_make_server_info("srv-b"))
            await pool.disconnect_all()

            assert pool.connected_count == 0
            adapter1.disconnect.assert_awaited_once()
            adapter2.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_all_empty(self):
        """空池断开不应报错"""
        pool = McpConnectionPool()
        await pool.disconnect_all()
        assert pool.connected_count == 0

    @pytest.mark.asyncio
    async def test_disconnect_all_with_errors(self):
        """某个断开失败不影响其他"""
        pool = McpConnectionPool()
        adapter1 = _make_mock_adapter()
        adapter1.disconnect = AsyncMock(
            side_effect=RuntimeError("断开失败")
        )
        adapter2 = _make_mock_adapter()

        with patch(
            "orchestrator.mcp_pool.McpClientAdapter",
            side_effect=[adapter1, adapter2],
        ):
            await pool.connect_server(_make_server_info("srv-a"))
            await pool.connect_server(_make_server_info("srv-b"))
            await pool.disconnect_all()

            # 两个都应被尝试断开
            adapter1.disconnect.assert_awaited_once()
            adapter2.disconnect.assert_awaited_once()
            assert pool.connected_count == 0
