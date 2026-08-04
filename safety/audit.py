"""
审计日志 — 兼容层，从 mcp_common.audit 重新导出。

所有审计功能已统一到 mcp_common/audit.py：
  - AuditLogger 类（链式哈希防篡改）
  - get_audit_logger() 单例工厂
  - audit_log() 便捷函数

用法（向后兼容）:
    from safety.audit import audit
    audit.log("write", "DB1.Motor", "1500", operator="ai")
"""

import json
import os
import sys

from mcp_common.audit import (
    AuditLogger,
    AuditStorageError,
    get_audit_logger,
    audit_log,
    _InterProcessLock,
    _compute_hash,
    _redact,
)


def _read_tail_hash(log_path, f) -> str:
    """从已打开（a+b 模式）的日志句柄读取链尾 hash。

    语义与 mcp_common/audit.py AuditLogger._load_last_hash 完全一致：
    链尾损坏（JSON 解析失败、缺少合法 hash 或崩溃残留半行）时 fail-closed
    抛 AuditStorageError，绝不静默回退零锚重起链；单条日志超过 64KB 时
    自动扩大读取窗口直到解析出完整末行。
    """
    f.seek(0, os.SEEK_END)
    size = f.tell()
    if size == 0:
        return "0" * 64
    window = 65536
    last_error = None
    while True:
        read_from = max(0, size - window)
        f.seek(read_from)
        tail = f.read(size - read_from).decode("utf-8", errors="replace")
        lines = [l for l in tail.splitlines() if l.strip()]
        if not lines:
            if read_from == 0:
                # 非空文件但整个窗口内无任何非空行：链尾已损坏
                # （如日志被截断成单个换行）。此时静默回退零锚会让
                # "截断旧链 + 重锚追加"的篡改逃过 verify()，必须 fail-closed。
                raise AuditStorageError(
                    f"审计日志链尾缺少任何合法条目，拒绝静默重锚: {log_path}"
                )
            window *= 4
            continue
        try:
            last = json.loads(lines[-1])
        except json.JSONDecodeError as exc:
            last_error = exc
        else:
            entry_hash = last.get("hash") if isinstance(last, dict) else None
            if not isinstance(entry_hash, str) or len(entry_hash) != 64:
                raise AuditStorageError(
                    f"审计日志链尾缺少合法 hash，拒绝静默重锚: {log_path}"
                )
            return entry_hash
        if read_from == 0:
            break
        window *= 4
    raise AuditStorageError(
        "审计日志链尾损坏，拒绝静默重锚续链: "
        f"{log_path}"
        + (f"（最后错误: {last_error}）" if last_error else "")
    )


def _write_entry_optimized(self: AuditLogger, entry: dict) -> dict:
    """AuditLogger._write_entry 的优化实现：锁内单次打开日志文件。

    基类实现每次写入要重开 3 次文件（lock 文件、rb 读链尾、a 追加）并 seek
    重读至多 65536 字节尾部取最后一行 hash，逐写入磁盘 I/O 叠加。本版把
    "读链尾 + 追加写"合并为一次 a+b 打开，逐写入文件打开次数从 3 降到 2。

    安全语义与基类完全一致：
      - 跨进程锁内以文件链尾为准续链（并发下内存 prev_hash 不可信）；
      - 链尾损坏/缺合法 hash 时 fail-closed 抛 AuditStorageError，不静默重锚；
      - 存储不可写（open/write/flush 失败）fail-closed 抛 AuditStorageError。
    """
    entry = _redact(entry)
    lock_path = self.path.with_name(self.path.name + ".lock")
    with _InterProcessLock(lock_path):
        try:
            with open(self.path, "a+b") as f:
                prev_hash = _read_tail_hash(self.path, f)
                entry["prev_hash"] = prev_hash
                body = {k: v for k, v in entry.items() if k != "hash"}
                entry["hash"] = _compute_hash(body, prev_hash, self._hmac_key)
                f.write((json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8"))
                f.flush()
        except OSError as e:
            print(f"[audit] 审计日志写入失败: {e}", file=sys.stderr)
            raise AuditStorageError(f"审计存储不可写: {e}") from e

    self._prev_hash = entry["hash"]
    return entry


# 覆盖基类写入路径：本兼容层导出的单例经 _write_entry 落盘，基类每写一次
# 重开 3 次文件并 seek 读尾，逐写入磁盘 I/O 叠加；此处替换为单次打开的优化
# 实现（安全语义不变）。mcp_common/audit.py 内建同款优化后应删除本补丁，
# 避免两份实现漂移。
AuditLogger._write_entry = _write_entry_optimized

# 全局单例（兼容现有代码: from safety.audit import audit）
_audit_logger: AuditLogger = get_audit_logger()
audit = _audit_logger

__all__ = [
    "AuditLogger",
    "get_audit_logger",
    "audit_log",
    "audit",
]
