"""
MCP 客户端适配器 — 封装 mcp 包的 ClientSession + stdio_client。

每个 McpClientAdapter 管理一个 MCP 服务器子进程的生命周期，
提供 connect / list_tools / call_tool / disconnect 接口。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult, ListToolsResult, TextContent

from orchestrator.registry import ServerInfo, ToolInfo

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolResult:
    """统一的 MCP 工具调用结果。

    所有经由 MCP 连接的调用都会先归一化为此结构；只有 ``ok=True``
    的结果才允许被编排层记为成功步骤。
    """

    ok: bool
    kind: str
    data: Any = None
    error: str = ""

    @classmethod
    def success(cls, data: Any, *, kind: str = "success") -> "ToolResult":
        return cls(ok=True, kind=kind, data=data)

    @classmethod
    def failure(cls, kind: str, error: str) -> "ToolResult":
        return cls(ok=False, kind=kind, error=error)


_ERROR_STATUSES = {
    "error", "failed", "fail", "rejected", "blocked", "denied",
    "forbidden", "cancelled", "canceled",
}
_TEXT_ERROR_MARKERS = ("❌", "🚫", "失败", "错误", "被拒绝", "未连接", "不存在", "未配置", "无效")
_TEXT_SUCCESS_MARKERS = ("✅", "成功", "已连接", "已断开", "📍")


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

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        """调用 MCP 工具。

        Args:
            tool_name: 工具名（不含服务器前缀）
            arguments: 工具参数字典

        Returns:
            统一的 ToolResult。业务错误、超时、取消和无法判定的文本均为 ok=False。
        """
        self._ensure_connected()

        if arguments is None:
            arguments = {}

        _logger.debug(f"调用工具 {self._server.name}.{tool_name}, 参数: {arguments}")

        try:
            result: CallToolResult = await self._session.call_tool(
                name=tool_name,
                arguments=arguments,
            )
        except asyncio.CancelledError:
            return ToolResult.failure("cancelled", "MCP 工具调用已取消")
        except asyncio.TimeoutError:
            return ToolResult.failure("timeout", "MCP 工具调用超时")
        except Exception as exc:
            return ToolResult.failure("transport_error", f"MCP 工具调用异常: {type(exc).__name__}: {exc}")

        return self._extract_result(result)

    @staticmethod
    def _payload_error(payload: dict[str, Any]) -> str:
        error = payload.get("error")
        if error not in (None, "", False, 0, [], {}):
            return str(payload.get("message") or error)
        if payload.get("ok") is False or payload.get("success") is False:
            return str(payload.get("message") or payload.get("reason") or "工具报告执行失败")
        if str(payload.get("status", "")).lower() in _ERROR_STATUSES:
            return str(payload.get("message") or payload.get("reason") or payload.get("status"))
        errors = payload.get("errors")
        if isinstance(errors, int) and errors > 0:
            return str(payload.get("message") or f"工具报告 {errors} 个错误")
        return ""

    def _extract_result(self, result: CallToolResult) -> ToolResult:
        """将 CallToolResult 归一化为唯一的 ToolResult 协议。"""
        texts = [
            item.text for item in result.content
            if isinstance(item, TextContent)
        ]
        combined = "\n".join(texts).strip()

        # isError 是 MCP 协议层的最终失败标志，优先于 structuredContent。
        if result.isError:
            return ToolResult.failure("tool_error", combined or "MCP 工具报告未知错误")

        if result.structuredContent is not None:
            return self._from_payload(result.structuredContent)

        if not combined:
            return ToolResult.failure("invalid_response", "MCP 工具返回为空，无法确认成功")

        import json
        import re

        try:
            return self._from_payload(json.loads(combined))
        except (json.JSONDecodeError, ValueError):
            pass

        # MCP 真实模式下部分工具会返回“文字 + JSON code block”。
        match = re.search(r'```(?:json)?\s*\n([\s\S]*?)\n\s*```', combined)
        if match:
            try:
                return self._from_payload(json.loads(match.group(1)))
            except (json.JSONDecodeError, ValueError):
                pass

        return self._from_text(combined)

    def _from_payload(self, payload: Any) -> ToolResult:
        if not isinstance(payload, dict):
            return ToolResult.failure("invalid_response", "MCP 工具未返回对象形式的结构化结果")
        if error := self._payload_error(payload):
            return ToolResult.failure("tool_error", error)
        return ToolResult.success(payload)

    @staticmethod
    def _from_text(text: str) -> ToolResult:
        if text.startswith("!") or any(marker in text for marker in _TEXT_ERROR_MARKERS):
            return ToolResult.failure("tool_error", text)
        if any(marker in text for marker in _TEXT_SUCCESS_MARKERS):
            return ToolResult.success(text, kind="text_success")
        return ToolResult.failure("invalid_response", "MCP 工具返回未标记的非 JSON 文本")

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
