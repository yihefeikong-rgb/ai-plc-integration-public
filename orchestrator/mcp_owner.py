"""防止多个进程同时拥有 MCP stdio 子进程。"""
from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


class McpOwnerBusyError(RuntimeError):
    """已有进程拥有 MCP 生命周期，当前进程必须停止启动。"""


def _pid_alive(pid: int) -> bool:
    """跨平台检查 PID 是否存活；无法确认时保守视为存活（fail-closed）。

    不发送实际信号、不终止进程，只判断该 PID 是否仍然存在。进程存在但
    不可访问（如权限不足）时也视为存活。

    POSIX 用 os.kill(pid, 0)（ESRCH 映射为 ProcessLookupError）。Windows 上
    os.kill(pid, 0) 对不存在的 PID 抛出的是普通 OSError（errno=EPERM，
    OpenProcess 失败被统一映射，从不抛 ProcessLookupError），若沿用统一的
    except OSError 会把它误判为存活，导致崩溃残留锁永远无法自动清理；
    因此 Windows 改用 OpenProcess 做存在性探测，仅当错误码明确表示进程
    不存在（ERROR_INVALID_PARAMETER=87）时判定已死，其余（含权限不足）
    一律视为存活。
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        _open_process = _kernel32.OpenProcess
        _open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        _open_process.restype = wintypes.HANDLE
        _close_handle = _kernel32.CloseHandle
        _close_handle.argtypes = (wintypes.HANDLE,)
        _close_handle.restype = wintypes.BOOL

        # PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = _open_process(0x1000, False, pid)
        if handle:
            _close_handle(handle)
            return True
        # 进程不存在 → ERROR_INVALID_PARAMETER；进程存在但权限不足 →
        # ERROR_ACCESS_DENIED，必须 fail-closed 视为存活。
        return ctypes.get_last_error() != 87
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


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
            # 锁文件已存在：仅当确认是崩溃进程的残留锁（PID 已死）时才清理并重试；
            # 无法确认、残留锁已被抢占或内容损坏时，一律 fail-closed 拒绝启动。
            if self._remove_stale_lock():
                try:
                    self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                except FileExistsError as retry_exc:
                    raise McpOwnerBusyError(
                        f"MCP 已由其他进程拥有: {self.lock_path}；请停止现有所有者后再启动。"
                    ) from retry_exc
            else:
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
            self._remove_lock_file(metadata, "abort")
            raise

    def release(self) -> None:
        if self._fd is None:
            return
        try:
            os.close(self._fd)
        finally:
            self._fd = None
        if self._metadata is None:
            return
        self._remove_lock_file(self._metadata, "released")

    def _remove_stale_lock(self) -> bool:
        """尝试清理崩溃进程残留的锁文件；锁路径可重新创建时返回 True。

        只有锁内容可解析、且其中 PID 确认已不存在时才清理；内容损坏、PID
        存活或无法确认时返回 False（调用方据此拒绝启动）。清理过程先把文件
        原子移开、确认移走的仍是刚读到的残留内容后才删除，避免误删竞争
        窗口内新建的活锁。
        """
        try:
            raw = self.lock_path.read_bytes()
        except OSError:
            return False
        try:
            pid = int(json.loads(raw.decode("utf-8"))["pid"])
        except (KeyError, TypeError, ValueError, UnicodeDecodeError):
            return False
        if _pid_alive(pid):
            return False
        trash = self.lock_path.with_name(
            f"{self.lock_path.name}.stale-{os.getpid()}-{time.monotonic_ns()}"
        )
        try:
            os.replace(self.lock_path, trash)
        except FileNotFoundError:
            return True  # 残留锁已被其他进程移除，路径空闲，可重试
        except OSError:
            return False
        try:
            moved = trash.read_bytes()
        except OSError:
            self._restore_lock(trash)
            return False
        if moved == raw:
            try:
                os.unlink(trash)
            except OSError:
                return False
            return True
        # 移走的不是刚读到的残留锁（已被新锁替换）：放回，交由 acquire 报忙。
        self._restore_lock(trash)
        return False

    def _remove_lock_file(self, expected: bytes, suffix: str) -> None:
        """原子移除锁文件：仅当路径上当前内容与 expected 一致时才删除。

        先把路径上的文件原子移到私有临时名再校验内容，避免“读取→unlink”
        窗口内第三方 acquire 时误删他人锁（TOCTOU）；移走的文件不是自己的
        则放回原路径，绝不删除。
        """
        trash = self.lock_path.with_name(
            f"{self.lock_path.name}.{suffix}-{os.getpid()}-{time.monotonic_ns()}"
        )
        try:
            os.replace(self.lock_path, trash)
        except FileNotFoundError:
            return  # 锁已不存在（崩溃清理或人工删除），无需处理
        try:
            if trash.read_bytes() == expected:
                try:
                    os.unlink(trash)
                except OSError:
                    pass
                return
        except OSError:
            pass
        # 移走的不是本进程创建的锁：放回原路径，绝不删除他人锁。
        self._restore_lock(trash)

    def _restore_lock(self, trash: Path) -> None:
        """把被临时移走的锁放回原路径；路径被占用或文件系统不支持时保留副本，绝不覆盖。"""
        try:
            os.link(trash, self.lock_path)
        except OSError:
            return  # 路径已被新锁占用（FileExistsError）或文件系统不支持硬链接：保留副本
        try:
            os.unlink(trash)
        except OSError:
            pass
