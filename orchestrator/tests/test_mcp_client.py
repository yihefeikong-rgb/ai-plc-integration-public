"""
测试 orchestrator.mcp_client — MCP 客户端适配器。

使用 mock MCP 服务器进行测试，无需真实 MCP 服务器进程。
通过模拟 stdio_client 和 ClientSession 来测试适配器逻辑。
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from orchestrator.registry import ServerInfo, ToolInfo
from orchestrator.mcp_client import McpClientAdapter, ToolResult


# ============================================================================
# 测试用的 ServerInfo 配置
# ============================================================================

@pytest.fixture
def test_server_info():
    return ServerInfo(
        name="test-mcp",
        description="测试 MCP 服务器",
        command="python",
        args=["server.py"],
        cwd="/fake/path",
    )


# ============================================================================
# 辅助：创建 mock MCP 会话
# ============================================================================

def _make_mock_tool(name: str, desc: str = "", input_schema: dict | None = None):
    """创建 mock Tool 对象"""
    from mcp.types import Tool
    return Tool(
        name=name,
        description=desc,
        inputSchema=input_schema or {"type": "object", "properties": {}},
    )


def _make_mock_call_result(text: str = "", is_error: bool = False, structured: dict | None = None):
    """创建 mock CallToolResult"""
    from mcp.types import CallToolResult, TextContent
    content = [TextContent(type="text", text=text)] if text else []
    return CallToolResult(
        content=content,
        structuredContent=structured,
        isError=is_error,
    )


def _make_mock_session(tools: list | None = None, call_result: dict | None = None):
    """创建 mock ClientSession"""
    session = AsyncMock()
    session.initialize = AsyncMock()

    if tools is not None:
        from mcp.types import ListToolsResult
        session.list_tools = AsyncMock(
            return_value=ListToolsResult(tools=tools)
        )
    else:
        session.list_tools = AsyncMock(
            return_value=MagicMock(tools=[])
        )

    if call_result is not None:
        session.call_tool = AsyncMock(return_value=call_result)
    else:
        session.call_tool = AsyncMock(
            return_value=_make_mock_call_result(text="ok")
        )

    return session


# ============================================================================
# Mock stdio_client 上下文管理器
# ============================================================================

class _MockStreamContext:
    """模拟 stdio_client 的 async context manager"""
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return (MagicMock(), MagicMock())

    async def __aexit__(self, *args):
        pass


class _MockSessionContext:
    """模拟 ClientSession 的 async context manager"""
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        pass


# ============================================================================
# McpClientAdapter 测试
# ============================================================================

class TestMcpClientAdapter:
    """McpClientAdapter 单元测试"""

    def test_create_adapter(self, test_server_info):
        adapter = McpClientAdapter(test_server_info)
        assert adapter.server_name == "test-mcp"
        assert adapter.is_connected is False

    @pytest.mark.asyncio
    async def test_connect(self, test_server_info):
        """测试连接流程"""
        session = _make_mock_session()

        with patch(
            "orchestrator.mcp_client.stdio_client",
            return_value=_MockStreamContext(session),
        ), patch(
            "orchestrator.mcp_client.ClientSession",
            return_value=_MockSessionContext(session),
        ):
            adapter = McpClientAdapter(test_server_info)
            await adapter.connect()

            assert adapter.is_connected is True
            session.initialize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_duplicate_skips(self, test_server_info):
        """重复连接应跳过"""
        session = _make_mock_session()

        with patch(
            "orchestrator.mcp_client.stdio_client",
            return_value=_MockStreamContext(session),
        ), patch(
            "orchestrator.mcp_client.ClientSession",
            return_value=_MockSessionContext(session),
        ):
            adapter = McpClientAdapter(test_server_info)
            await adapter.connect()
            await adapter.connect()  # 第二次连接

            assert adapter.is_connected is True
            # initialize 只应调用一次
            session.initialize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_tools(self, test_server_info):
        """测试工具发现"""
        mock_tools = [
            _make_mock_tool("read_tag", "读取 PLC 标签"),
            _make_mock_tool("write_tag", "写入 PLC 标签"),
        ]
        session = _make_mock_session(tools=mock_tools)

        with patch(
            "orchestrator.mcp_client.stdio_client",
            return_value=_MockStreamContext(session),
        ), patch(
            "orchestrator.mcp_client.ClientSession",
            return_value=_MockSessionContext(session),
        ):
            adapter = McpClientAdapter(test_server_info)
            await adapter.connect()
            tools = await adapter.list_tools()

            assert len(tools) == 2
            assert tools[0].name == "read_tag"
            assert tools[0].server == "test-mcp"
            assert tools[0].description == "读取 PLC 标签"
            assert tools[1].name == "write_tag"

    @pytest.mark.asyncio
    async def test_list_tools_not_connected_raises(self, test_server_info):
        """未连接时调用 list_tools 应报错"""
        adapter = McpClientAdapter(test_server_info)
        with pytest.raises(RuntimeError, match="未连接"):
            await adapter.list_tools()

    @pytest.mark.asyncio
    async def test_call_tool(self, test_server_info):
        """测试工具调用"""
        result = _make_mock_call_result(text='{"value": 42}')
        session = _make_mock_session(call_result=result)

        with patch(
            "orchestrator.mcp_client.stdio_client",
            return_value=_MockStreamContext(session),
        ), patch(
            "orchestrator.mcp_client.ClientSession",
            return_value=_MockSessionContext(session),
        ):
            adapter = McpClientAdapter(test_server_info)
            await adapter.connect()
            resp = await adapter.call_tool("read_tag", {"tag": "DB1.MotorSpeed"})

            assert isinstance(resp, ToolResult)
            assert resp.ok is True
            assert resp.data == {"value": 42}
            session.call_tool.assert_awaited_once_with(
                name="read_tag",
                arguments={"tag": "DB1.MotorSpeed"},
            )

    @pytest.mark.asyncio
    async def test_call_tool_with_empty_args(self, test_server_info):
        """测试无参数工具调用"""
        result = _make_mock_call_result(text='{"ok": true}')
        session = _make_mock_session(call_result=result)

        with patch(
            "orchestrator.mcp_client.stdio_client",
            return_value=_MockStreamContext(session),
        ), patch(
            "orchestrator.mcp_client.ClientSession",
            return_value=_MockSessionContext(session),
        ):
            adapter = McpClientAdapter(test_server_info)
            await adapter.connect()
            resp = await adapter.call_tool("ping")

            assert resp.ok is True
            assert resp.data == {"ok": True}
            session.call_tool.assert_awaited_once_with(
                name="ping",
                arguments={},
            )

    @pytest.mark.asyncio
    async def test_call_tool_structured_content(self, test_server_info):
        """测试带 structuredContent 的返回"""
        from mcp.types import CallToolResult
        result = CallToolResult(
            content=[],
            structuredContent={"status": "compiled", "errors": 0},
        )
        session = _make_mock_session(call_result=result)

        with patch(
            "orchestrator.mcp_client.stdio_client",
            return_value=_MockStreamContext(session),
        ), patch(
            "orchestrator.mcp_client.ClientSession",
            return_value=_MockSessionContext(session),
        ):
            adapter = McpClientAdapter(test_server_info)
            await adapter.connect()
            resp = await adapter.call_tool("compile")

            assert resp.ok is True
            assert resp.data == {"status": "compiled", "errors": 0}

    @pytest.mark.asyncio
    async def test_call_tool_error_result(self, test_server_info):
        """测试工具返回错误的情况"""
        result = _make_mock_call_result(
            text="工具执行失败: 项目未打开",
            is_error=True,
        )
        session = _make_mock_session(call_result=result)

        with patch(
            "orchestrator.mcp_client.stdio_client",
            return_value=_MockStreamContext(session),
        ), patch(
            "orchestrator.mcp_client.ClientSession",
            return_value=_MockSessionContext(session),
        ):
            adapter = McpClientAdapter(test_server_info)
            await adapter.connect()
            resp = await adapter.call_tool("bad_tool")

            assert resp.ok is False
            assert resp.kind == "tool_error"
            assert "项目未打开" in resp.error

    @pytest.mark.asyncio
    async def test_call_tool_not_connected_raises(self, test_server_info):
        """未连接时调用 call_tool 应报错"""
        adapter = McpClientAdapter(test_server_info)
        with pytest.raises(RuntimeError, match="未连接"):
            await adapter.call_tool("test", {})

    @pytest.mark.asyncio
    async def test_disconnect(self, test_server_info):
        """测试断开连接"""
        session = _make_mock_session()

        with patch(
            "orchestrator.mcp_client.stdio_client",
            return_value=_MockStreamContext(session),
        ), patch(
            "orchestrator.mcp_client.ClientSession",
            return_value=_MockSessionContext(session),
        ):
            adapter = McpClientAdapter(test_server_info)
            await adapter.connect()
            await adapter.disconnect()

            assert adapter.is_connected is False

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, test_server_info):
        """未连接时断开不应报错"""
        adapter = McpClientAdapter(test_server_info)
        await adapter.disconnect()  # 不应抛出异常
        assert adapter.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_failure_cleanup(self, test_server_info):
        """连接失败时清理资源"""
        session = _make_mock_session()
        session.initialize = AsyncMock(side_effect=RuntimeError("连接失败"))

        with patch(
            "orchestrator.mcp_client.stdio_client",
            return_value=_MockStreamContext(session),
        ), patch(
            "orchestrator.mcp_client.ClientSession",
            return_value=_MockSessionContext(session),
        ):
            adapter = McpClientAdapter(test_server_info)
            with pytest.raises(RuntimeError, match="连接失败"):
                await adapter.connect()

            assert adapter.is_connected is False

    @pytest.mark.asyncio
    async def test_call_tool_plain_text_result(self, test_server_info):
        """测试纯文本返回（非 JSON）"""
        result = _make_mock_call_result(text="操作成功完成")
        session = _make_mock_session(call_result=result)

        with patch(
            "orchestrator.mcp_client.stdio_client",
            return_value=_MockStreamContext(session),
        ), patch(
            "orchestrator.mcp_client.ClientSession",
            return_value=_MockSessionContext(session),
        ):
            adapter = McpClientAdapter(test_server_info)
            await adapter.connect()
            resp = await adapter.call_tool("simple_tool")

            assert resp.ok is True
            assert resp.kind == "text_success"
            assert resp.data == "操作成功完成"


# ============================================================================
# McpClientAdapter._extract_result 测试
# ============================================================================

class TestExtractResult:
    """测试结果提取逻辑"""

    def test_extract_structured_content(self):
        from mcp.types import CallToolResult
        result = CallToolResult(
            content=[],
            structuredContent={"a": 1, "b": 2},
        )
        adapter = McpClientAdapter.__new__(McpClientAdapter)
        extracted = adapter._extract_result(result)
        assert extracted.ok is True
        assert extracted.data == {"a": 1, "b": 2}

    def test_extract_json_text(self):
        from mcp.types import CallToolResult, TextContent
        result = CallToolResult(
            content=[TextContent(type="text", text='{"key": "value"}')],
        )
        adapter = McpClientAdapter.__new__(McpClientAdapter)
        extracted = adapter._extract_result(result)
        assert extracted.ok is True
        assert extracted.data == {"key": "value"}

    def test_extract_plain_text(self):
        from mcp.types import CallToolResult, TextContent
        result = CallToolResult(
            content=[TextContent(type="text", text="hello world")],
        )
        adapter = McpClientAdapter.__new__(McpClientAdapter)
        extracted = adapter._extract_result(result)
        assert extracted.ok is False
        assert extracted.kind == "invalid_response"

    def test_extract_empty_content(self):
        from mcp.types import CallToolResult
        result = CallToolResult(content=[])
        adapter = McpClientAdapter.__new__(McpClientAdapter)
        extracted = adapter._extract_result(result)
        assert extracted.ok is False
        assert extracted.kind == "invalid_response"

    def test_extract_error_with_text(self):
        from mcp.types import CallToolResult, TextContent
        result = CallToolResult(
            content=[TextContent(type="text", text="编译错误: 语法错误")],
            isError=True,
        )
        adapter = McpClientAdapter.__new__(McpClientAdapter)
        extracted = adapter._extract_result(result)
        assert extracted.ok is False
        assert extracted.kind == "tool_error"
        assert "编译错误" in extracted.error

    def test_extract_error_no_text(self):
        from mcp.types import CallToolResult
        result = CallToolResult(content=[], isError=True)
        adapter = McpClientAdapter.__new__(McpClientAdapter)
        extracted = adapter._extract_result(result)
        assert extracted.ok is False
        assert extracted.kind == "tool_error"
        assert extracted.error == "MCP 工具报告未知错误"

    def test_extract_markdown_code_block_json(self):
        """MCP 真实模式下 \"✅ 成功\\n```json\\n{...}\\n```\" 应提取 JSON"""
        from mcp.types import CallToolResult, TextContent
        result = CallToolResult(
            content=[TextContent(
                type="text",
                text='✅ 成功\n```json\n{"success": true, "errors": 0, "error_list": []}\n```'
            )],
        )
        adapter = McpClientAdapter.__new__(McpClientAdapter)
        extracted = adapter._extract_result(result)
        assert extracted.ok is True
        assert extracted.data == {"success": True, "errors": 0, "error_list": []}

    def test_extract_markdown_code_block_no_lang(self):
        """无语言标注的 code block 也能提取"""
        from mcp.types import CallToolResult, TextContent
        result = CallToolResult(
            content=[TextContent(
                type="text",
                text='Done.\n```\n{"ok": true, "count": 42}\n```'
            )],
        )
        adapter = McpClientAdapter.__new__(McpClientAdapter)
        extracted = adapter._extract_result(result)
        assert extracted.ok is True
        assert extracted.data == {"ok": True, "count": 42}

    def test_extract_markdown_no_code_block_falls_back(self):
        """无 code block 的纯文本仍走降级路径"""
        from mcp.types import CallToolResult, TextContent
        result = CallToolResult(
            content=[TextContent(type="text", text="操作完成，但这是纯文本")],
        )
        adapter = McpClientAdapter.__new__(McpClientAdapter)
        extracted = adapter._extract_result(result)
        assert extracted.ok is False
        assert extracted.kind == "invalid_response"
