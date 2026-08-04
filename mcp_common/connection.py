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
import weakref
from typing import Any, Callable, Coroutine, TypeVar

T = TypeVar("T")


class ConnectionManager:
    """线程安全的惰性单例连接管理器。

    使用双锁策略：
      - threading.Lock 保护同步路径 (get_sync) 与 _instance 的跨路径赋值
      - asyncio.Lock 按事件循环分别创建，保护异步路径 (get)，避免阻塞事件循环
    """

    def __init__(self, connect_fn: Callable):
        self._connect_fn = connect_fn
        self._instance: Any = None
        self._generation = 0
        self._sync_lock = threading.Lock()
        # 每个事件循环一把 asyncio.Lock，避免跨事件循环共用锁触发 RuntimeError
        self._async_locks = weakref.WeakKeyDictionary()  # event loop -> asyncio.Lock

    def _get_async_lock(self) -> asyncio.Lock:
        """按事件循环惰性创建 asyncio.Lock（必须在事件循环中调用）"""
        loop = asyncio.get_running_loop()
        with self._sync_lock:
            lock = self._async_locks.get(loop)
            if lock is None:
                lock = asyncio.Lock()
                self._async_locks[loop] = lock
            return lock

    def get_sync(self):
        """同步获取连接（常用于 Modbus 等同步客户端）"""
        if self._instance is None:
            with self._sync_lock:
                if self._instance is None:
                    self._instance = self._connect_fn()
        return self._instance

    async def get(self):
        """异步获取连接（常用于 asyncio 连接）"""
        while True:
            if self._instance is not None:
                return self._instance
            async with self._get_async_lock():
                with self._sync_lock:
                    if self._instance is not None:
                        return self._instance
                    # 记录本连接所属的代次，用于识别建连期间是否发生过 reset()
                    gen = self._generation
                result = self._connect_fn()
                if hasattr(result, "__await__"):
                    result = await result
                with self._sync_lock:
                    if self._instance is None and self._generation == gen:
                        self._instance = result
                        return result
                # 竞态已发生：建连期间其他路径已抢先建立连接，或 reset() 已使
                # 本连接失效。本连接是失败方，必须关闭以防 socket 泄漏。
                await self._close_connection(result)
                # 回到循环：实例已建立则返回，否则按 reset() 后的新代次重连

    async def _close_connection(self, conn: Any) -> None:
        """尽力关闭被丢弃的连接，避免 socket/句柄泄漏。

        connect_fn 返回类型不确定（async 流 / 同步客户端等），按常见
        关闭入口依次尝试（aclose / close / disconnect），失败不抛错。
        """
        if conn is None:
            return
        items = conn if isinstance(conn, (tuple, list)) else (conn,)
        for item in items:
            if item is None:
                continue
            closer = None
            for name in ("aclose", "close", "disconnect"):
                closer = getattr(item, name, None)
                if closer is not None:
                    break
            if closer is None:
                continue
            try:
                res = closer()
                if hasattr(res, "__await__"):
                    await asyncio.wait_for(res, timeout=5.0)
            except Exception:
                pass
            # asyncio.StreamWriter: close() 后等待底层 socket 真正关闭
            wait_closed = getattr(item, "wait_closed", None)
            if wait_closed is not None:
                try:
                    await asyncio.wait_for(wait_closed(), timeout=5.0)
                except Exception:
                    pass

    def reset(self):
        """重置连接，下次访问时重新初始化"""
        with self._sync_lock:
            self._generation += 1
            self._instance = None

    @property
    def connected(self) -> bool:
        with self._sync_lock:
            return self._instance is not None
