"""
审计日志模块 — 所有关键操作自动记录到 JSON Lines 文件。

用法:
    from audit import audit_log
    audit_log("create_ladder_block", user_input="电机正反转", block_name="MotorFwdRev", result="ok")

输出 (audit.log):
    {"timestamp": "2026-06-03T12:00:00.123Z", "operation": "create_ladder_block", ...}
"""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _get_log_path() -> str:
    """获取审计日志路径（惰性读取 config）"""
    try:
        from config_loader import cfg
        return cfg.logging.audit_log
    except Exception:
        return str(Path(__file__).parent / "logs" / "audit.log")


def audit_log(operation: str, **kwargs: Any) -> None:
    """记录一条审计日志。

    Args:
        operation: 操作类型，如 "create_ladder_block", "full_pipeline", "import_scl"
        **kwargs: 任意附加字段（user_input, block_name, result, error, duration_ms 等）
    """
    log_path = _get_log_path()
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") +
                     f"{int(time.time() * 1000) % 1000:03d}Z",
        "operation": operation,
        **kwargs,
    }

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            f.flush()
    except Exception:
        pass  # 审计日志失败不应阻塞主流程


def read_logs(operation: str = None, limit: int = 50) -> list:
    """读取最近的审计日志（调试用）。

    Args:
        operation: 按操作类型过滤（可选）
        limit: 最多返回条数
    """
    log_path = _get_log_path()
    if not os.path.exists(log_path):
        return []

    entries = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if operation and entry.get("operation") != operation:
                    continue
                entries.append(entry)
            except json.JSONDecodeError:
                continue

    return entries[-limit:]
