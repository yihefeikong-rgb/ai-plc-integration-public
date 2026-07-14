"""防止多个进程同时拥有 MCP stdio 子进程。"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


class McpOwnerBusyError(RuntimeError):
    """已有进程拥有 MCP 生命周期，当前进程必须停止启动。"""


class McpOwnerLock:
    """使用独占文件创建实现跨进程 MCP 所有权锁。"""

    def __init__(self, owner: str, *, lock_path: Path | None = None):
        self.owner = owner
        configured_path = os.environ.get("AI_PLC_MCP_OWNER_LOCK", "")
        self.lock_path = lock_path or Path(configured_path or (Path(tempfile.gettempdir()) / "ai-plc-mcp-owner.lock"))
        self._fd: int | None = None
        self._metadata: bytes | None = None

    def acquire(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        metadata = json.dumps(
            {
                "owner": self.owner,
                "pid": os.getpid(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
        ).encode("utf-8")
        try:
            self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise McpOwnerBusyError(
                f"MCP 已由其他进程拥有: {self.lock_path}；请停止现有所有者后再启动。"
            ) from exc
        try:
            os.write(self._fd, metadata)
            os.fsync(self._fd)
            self._metadata = metadata
        except Exception:
            os.close(self._fd)
            self._fd = None
            try:
                self.lock_path.unlink()
            except OSError:
                pass
            raise

    def release(self) -> None:
        if self._fd is None:
            return
        try:
            os.close(self._fd)
        finally:
            self._fd = None
        try:
            if self._metadata is not None and self.lock_path.read_bytes() == self._metadata:
                self.lock_path.unlink()
        except FileNotFoundError:
            pass
