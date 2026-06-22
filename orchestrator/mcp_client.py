"""
MCP 客户端适配器 — 封装 mcp 包的 ClientSession + stdio_client。

每个 McpClientAdapter 管理一个 MCP 服务器子进程的生命周期，
提供 connect / list_tools / call_tool / disconnect 接口。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult, ListToolsResult, TextContent

from orchestrator.registry import ServerInfo, ToolInfo

_logger = logging.getLogger(__name__)


class McpClientAdapter:
    """单个 MCP 服务器的客户端适配器。

    管理 MCP 服务器子进程的启动、连接、工具发现和调用。

    使用方式:
        adapter = McpClientAdapter(server_info)
        await adapter.connect()
        tools = await adapter.list_tools()
        result = await adapter.call_tool("plc_read", {"tag": "DB1.x"})
        await adapter.disconnect()
    """

    def __init__(self, server_info: ServerInfo):
        self._server = server_info
        self._session: ClientSession | None = None
        self._read_stream = None
        self._write_stream = None
        self._stdio_context = None  # 持有 stdio_client 的 async context manager
        self._session_context = None  # 持有 ClientSession 的 async context manager
        self._connected = False

    @property
    def server_name(self) -> str:
        return self._server.name

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """启动 MCP 服务器子进程并建立连接。

        通过 stdio 协议启动子进程，创建 ClientSession 并完成初始化握手。
        """
        if self._connected:
            _logger.warning(f"服务器 {self._server.name} 已连接，跳过重复连接")
            return

        params = StdioServerParameters(
            command=self._server.command,
            args=self._server.args,
            cwd=self._server.cwd or None,
        )

        _logger.info(
            f"正在启动 MCP 服务器: {self._server.name} "
            f"({self._server.command} {' '.join(self._server.args)})"
        )

        try:
            # 启动子进程，建立 stdio 双向流
            self._stdio_context = stdio_client(params)
            self._read_stream, self._write_stream = await self._stdio_context.__aenter__()

            # 创建 ClientSession 并初始化
            self._session_context = ClientSession(
                self._read_stream, self._write_stream
            )
            self._session = await self._session_context.__aenter__()
            await self._session.initialize()

            self._connected = True
            _logger.info(f"MCP 服务器 {self._server.name} 连接成功")
        except Exception:
            # 连接失败时清理已创建的资源
            await self._cleanup_on_error()
            raise

    async def list_tools(self) -> list[ToolInfo]:
        """从服务器发现工具列表。

        Returns:
            ToolInfo 列表，server 字段已设为当前服务器名
        """
        self._ensure_connected()
        result: ListToolsResult = await self._session.list_tools()

        tools = []
        for tool in result.tools:
            tools.append(
                ToolInfo(
                    name=tool.name,
                    description=tool.description or "",
                    server=self._server.name,
                    parameters=tool.inputSchema,
                )
            )
        return tools

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """调用 MCP 工具。

        Args:
            tool_name: 工具名（不含服务器前缀）
            arguments: 工具参数字典

        Returns:
            工具的返回结果字典，包含成功时解析出的数据或错误信息
        """
        self._ensure_connected()

        if arguments is None:
            arguments = {}

        _logger.debug(f"调用工具 {self._server.name}.{tool_name}, 参数: {arguments}")

        result: CallToolResult = await self._session.call_tool(
            name=tool_name,
            arguments=arguments,
        )

        return self._extract_result(result)

    def _extract_result(self, result: CallToolResult) -> dict[str, Any]:
        """从 CallToolResult 中提取可用数据。

        MCP 工具返回 content 列表（TextContent/ImageContent 等），
        我们优先提取 structuredContent，其次拼接文本内容。
        """
        # 如果有结构化内容，优先使用
        if result.structuredContent:
            return result.structuredContent

        # 拼接所有文本内容
        texts = []
        for item in result.content:
            if isinstance(item, TextContent):
                texts.append(item.text)

        if result.isError:
            return {"error": True, "message": "\n".join(texts) if texts else "未知错误"}

        # 尝试解析 JSON 文本
        if texts:
            import json

            combined = "\n".join(texts)
            try:
                return json.loads(combined)
            except (json.JSONDecodeError, ValueError):
                return {"text": combined}

        return {"text": ""}

    def _ensure_connected(self) -> None:
        """确保已连接，否则抛出明确错误"""
        if not self._connected:
            raise RuntimeError(
                f"MCP 服务器 {self._server.name} 未连接，请先调用 connect()"
            )

    async def disconnect(self) -> None:
        """断开连接并终止子进程。"""
        if not self._connected:
            return

        _logger.info(f"正在断开 MCP 服务器: {self._server.name}")

        errors = []

        # 关闭 session
        if self._session_context:
            try:
                await self._session_context.__aexit__(None, None, None)
            except Exception as e:
                errors.append(f"session: {e}")
            self._session_context = None

        # 关闭 stdio 流
        if self._stdio_context:
            try:
                await self._stdio_context.__aexit__(None, None, None)
            except Exception as e:
                errors.append(f"stdio: {e}")
            self._stdio_context = None

        self._session = None
        self._read_stream = None
        self._write_stream = None
        self._connected = False

        if errors:
            _logger.warning(f"断开 {self._server.name} 时有错误: {'; '.join(errors)}")
        else:
            _logger.info(f"MCP 服务器 {self._server.name} 已断开")

    async def _cleanup_on_error(self) -> None:
        """连接失败时清理资源"""
        # 尝试关闭 session
        if self._session_context:
            try:
                await self._session_context.__aexit__(None, None, None)
            except Exception:
                pass
            self._session_context = None

        # 尝试关闭 stdio
        if self._stdio_context:
            try:
                await self._stdio_context.__aexit__(None, None, None)
            except Exception:
                pass
            self._stdio_context = None

        self._session = None
        self._read_stream = None
        self._write_stream = None
        self._connected = False