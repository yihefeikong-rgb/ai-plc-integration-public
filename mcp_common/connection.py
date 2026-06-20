"""
惰性单例连接管理器 — 为 mitsubishi-mcp/modbus-mcp/opcua-mcp 提供统一连接模式。

消除了 three 个 server 中重复的 get_connection()/get_client() 模式。

用法:
    from mcp_common.connection import ConnectionManager

    # 模式1: async 连接（三菱/OPC UA）
    mgr = ConnectionManager(connect_fn=my_async_connect)
    reader, writer = await mgr.get()

    # 模式2: sync 连接（Modbus）
    mgr = ConnectionManager(connect_fn=my_sync_connect)
    client = mgr.get_sync()

    # 重置/重新连接
    mgr.reset()
"""

import asyncio
import threading
from typing import Any, Callable, Coroutine, Optional, TypeVar

T = TypeVar("T")


class ConnectionManager:
    """线程安全的惰性单例连接管理器。

    使用双锁策略：
      - threading.Lock 保护同步路径 (get_sync)
      - asyncio.Lock 保护异步路径 (get)，避免阻塞事件循环
    """

    def __init__(self, connect_fn: Callable):
        self._connect_fn = connect_fn
        self._instance: Any = None
        self._sync_lock = threading.Lock()
        self._async_lock: Optional[asyncio.Lock] = None

    def _get_async_lock(self) -> asyncio.Lock:
        """惰性创建 asyncio.Lock（必须在事件循环中调用）"""
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock

    def get_sync(self):
        """同步获取连接（常用于 Modbus 等同步客户端）"""
        if self._instance is None:
            with self._sync_lock:
                if self._instance is None:
                    self._instance = self._connect_fn()
        return self._instance

    async def get(self):
        """异步获取连接（常用于 asyncio 连接）"""
        if self._instance is None:
            async with self._get_async_lock():
                if self._instance is None:
                    result = self._connect_fn()
                    if hasattr(result, "__await__"):
                        self._instance = await result
                    else:
                        self._instance = result
        return self._instance

    def reset(self):
        """重置连接，下次访问时重新初始化"""
        with self._sync_lock:
            self._instance = None

    @property
    def connected(self) -> bool:
        return self._instance is not None
