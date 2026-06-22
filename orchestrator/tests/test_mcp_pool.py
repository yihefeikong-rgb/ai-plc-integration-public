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