"""
编排层启动引导 — 连接所有 MCP 服务器、注册工具和工作流。

提供 bootstrap() 和 shutdown() 两个入口，
分别用于启动和关闭编排层。
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from orchestrator.mcp_pool import McpConnectionPool
from orchestrator.registry import ToolInfo, get_registry

_logger = logging.getLogger(__name__)


@dataclass
class BootstrapResult:
    """启动引导结果"""

    connected: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


async def bootstrap(
    pool: Any = None,
    engine: Any = None,
    server_list: list[Any] | None = None,
) -> BootstrapResult:
    """启动编排层：连接所有 MCP 服务器、注册工具和工作流。

    单个服务器连接失败时记录警告，继续处理其他服务器。

    Args:
        pool: MCP 连接池，默认新建 McpConnectionPool
        engine: 编排引擎，默认使用全局单例 get_engine()
        server_list: 要连接的服务器列表，默认使用 ALL_SERVERS

    Returns:
        BootstrapResult 包含连接成功和失败的服务器信息
    """
    from orchestrator.core import get_engine
    from orchestrator.server_configs import ALL_SERVERS
    from orchestrator.workflows import register_all_workflows

    if pool is None:
        pool = McpConnectionPool()
    if engine is None:
        engine = get_engine()
    if server_list is None:
        server_list = ALL_SERVERS

    result = BootstrapResult()
    registry = get_registry()

    # 逐个连接服务器并注册工具
    for info in server_list:
        try:
            await asyncio.wait_for(pool.connect_server(info), timeout=10.0)
            adapter = pool.get_adapter(info.name)
            tools: list = []
            if adapter is not None:
                tools = await asyncio.wait_for(adapter.list_tools(), timeout=5.0)
                for tool in tools:
                    registry.register_tool(info.name, tool)
            result.connected.append(info.name)
            _logger.info(f"服务器 {info.name} 已连接并注册 {len(tools)} 个工具")
        except asyncio.TimeoutError:
            _logger.warning(f"服务器 {info.name} 连接超时")
            result.failed.append((info.name, "连接超时"))
            # 清理可能残留的子进程
            try:
                await pool.disconnect_server(info.name)
            except Exception:
                pass
        except Exception as e:
            _logger.warning(f"服务器 {info.name} 连接失败: {e}")
            result.failed.append((info.name, str(e)))

    # 注册所有工作流
    register_all_workflows(engine)
    _logger.info(
        f"启动引导完成: {len(result.connected)} 连接, {len(result.failed)} 失败"
    )

    return result


async def shutdown(pool: Any = None) -> None:
    """关闭编排层：断开所有 MCP 服务器连接。

    Args:
        pool: MCP 连接池，默认新建 McpConnectionPool
    """
    if pool is None:
        pool = McpConnectionPool()

    await pool.disconnect_all()
    _logger.info("编排层已关闭")
