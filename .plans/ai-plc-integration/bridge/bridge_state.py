"""Bridge 状态文件的单一枚举、原子写入与互斥锁。"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


ACTIVE_STAGES = frozenset({"NEED_CODEX_PLAN", "NEED_CLAUDE", "NEED_CODEX_REVIEW"})
STOP_STAGES = frozenset({"DONE", "BLOCKED", "SAFETY_BLOCK"})
KNOWN_STAGES = ACTIVE_STAGES | STOP_STAGES
REVIEWABLE_STAGE = "NEED_CODEX_REVIEW"


class BridgeStateError(RuntimeError):
    """状态结构、锁或持久化不满足 Bridge 协议。"""


def _lock_path(state_file: Path) -> Path:
    return state_file.with_name(f"{state_file.name}.lock")


@contextmanager
def state_lock(state_file: Path) -> Iterator[None]:
    """用 O_EXCL 创建进程互斥锁；异常遗留锁必须人工处理，不能静默抢锁。"""
    lock_file = _lock_path(state_file)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise BridgeStateError(f"Bridge 状态已被其他运行者锁定: {lock_file}") from exc
    try:
        metadata = {
            "pid": os.getpid(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        os.write(fd, json.dumps(metadata, ensure_ascii=False).encode("utf-8"))
        os.fsync(fd)
        yield
    finally:
        os.close(fd)
        try:
            lock_file.unlink()
        except FileNotFoundError:
            pass


def read_state(state_file: Path, *, default: dict | None = None) -> dict:
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if default is not None:
            return dict(default)
        raise BridgeStateError(f"state.json not found: {state_file}")
    except json.JSONDecodeError as exc:
        raise BridgeStateError(f"state.json is invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise BridgeStateError("state.json root must be an object")
    return data


def write_text_atomic(path: Path, content: str) -> None:
    """同目录临时文件 + fsync + replace，避免半写入的审查产物。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def write_state_atomic(state_file: Path, state: dict) -> None:
    write_text_atomic(state_file, json.dumps(state, indent=2, ensure_ascii=False) + "\n")


@contextmanager
def locked_state(state_file: Path, *, default: dict | None = None) -> Iterator[dict]:
    """锁住 read-modify-write 临界区；正常退出时一次性持久化。"""
    with state_lock(state_file):
        state = read_state(state_file, default=default)
        yield state
        write_state_atomic(state_file, state)


def artifact_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError as exc:
        raise BridgeStateError(f"required review artifact missing: {path}") from exc


def validate_state_shape(state: dict) -> tuple[str, str]:
    stage = state.get("stage")
    owner = state.get("owner")
    if not isinstance(stage, str) or stage not in KNOWN_STAGES:
        raise BridgeStateError(f"unsupported stage: {stage!r}")
    if not isinstance(owner, str) or not owner:
        raise BridgeStateError("state owner is missing")
    return stage, owner
