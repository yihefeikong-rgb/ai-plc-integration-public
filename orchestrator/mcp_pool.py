"""
MCP 连接池 — 管理多个 MCP 服务器连接的生命周期。

提供统一接口来连接多个服务器、调用工具和断开连接。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from orchestrator.mcp_client import McpClientAdapter
from orchestrator.registry import ServerInfo

_logger = logging.getLogger(__name__)


class McpConnectionPool:
    """管理多个 MCP 服务器的连接池。

    使用方式:
        pool = McpConnectionPool()
        await pool.connect_server(plc_bridge_info)
        await pool.connect_server(tia_mcp_info)
        result = await pool.call_tool("plc-mcp-bridge", "s7_read", {"tag": "DB1.x"})
        await pool.disconnect_all()
    """

    def __init__(self):
        self._adapters: dict[str, McpClientAdapter] = {}

    @property
    def server_names(self) -> list[str]:
        """已连接的服务器名称列表"""
        return list(self._adapters.keys())

    @property
    def connected_count(self) -> int:
        """已连接服务器数量"""
        return len(self._adapters)

    async def connect_server(self, server_info: ServerInfo) -> None:
        """连接一个 MCP 服务器。

        如果同名服务器已连接，则跳过（不重复连接）。

        Args:
            server_info: 服务器配置信息（含 command/args/cwd）
        """
        if server_info.name in self._adapters:
            _logger.warning(f"服务器 {server_info.name} 已在连接池中，跳过")
            return

        adapter = McpClientAdapter(server_info)
        await adapter.connect()

        self._adapters[server_info.name] = adapter
        _logger.info(f"服务器 {server_info.name} 已加入连接池")

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """通过连接池调用指定服务器的工具。

        Args:
            server_name: MCP 服务器名
            tool_name: 工具名
            arguments: 工具参数字典

        Returns:
            工具返回结果字典

        Raises:
            RuntimeError: 服务器未连接
        """
        adapter = self._adapters.get(server_name)
        if adapter is None:
            raise RuntimeError(
                f"服务器 {server_name} 未在连接池中。"
                f"已连接的服务器: {list(self._adapters.keys())}"
            )

        return await adapter.call_tool(tool_name, arguments)

    def get_adapter(self, server_name: str) -> McpClientAdapter | None:
        """获取指定服务器的适配器"""
        return self._adapters.get(server_name)

    async def disconnect_server(self, server_name: str) -> None:
        """断开指定服务器的连接"""
        adapter = self._adapters.pop(server_name, None)
        if adapter:
            await adapter.disconnect()
            _logger.info(f"服务器 {server_name} 已从连接池移除")

    async def disconnect_all(self) -> None:
        """断开所有连接"""
        _logger.info(f"正在断开所有 {len(self._adapters)} 个连接...")
        adapters = list(self._adapters.values())
        self._adapters.clear()

        # 并行断开所有连接
        await asyncio.gather(
            *(adapter.disconnect() for adapter in adapters),
            return_exceptions=True,
        )
        _logger.info("所有连接已断开")