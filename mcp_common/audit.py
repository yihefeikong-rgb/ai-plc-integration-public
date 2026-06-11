"""
统一审计日志模块 — 合并 safety/audit.py 和 tia-mcp/audit.py 的功能。

特性:
  - 链式哈希防篡改（来自 safety/audit.py）
  - 灵活的 log() 方法，支持 operation/action 双命名
  - 从配置文件读取日志路径（来自 tia-mcp/audit.py）
  - 向后兼容的 audit_log() 便捷函数

用法:
    from mcp_common.audit import get_audit_logger

    logger = get_audit_logger()
    logger.log("write", "DB1.Motor", "1500", operator="ai")
    logger.log_operation("create_ladder_block", block_name="MotorFwdRev", result="ok")
"""

import json
import hashlib
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


def _compute_hash(entry: dict, prev_hash: str) -> str:
    payload = json.dumps(entry, sort_keys=True) + prev_hash
    return hashlib.sha256(payload.encode()).hexdigest()


class AuditLogger:
    """不可篡改的审计日志（链式哈希 + JSON Lines）

    同时支持两种调用风格:
      1. logger.log("write", "tag", "value")            # 兼容 safety/audit.py
      2. logger.log_operation("import_scl", ...)         # 兼容 tia-mcp/audit.py
    """

    def __init__(self, log_path: str = ""):
        if log_path:
            self.path = Path(log_path)
        else:
            self.path = Path(__file__).parent.parent / "logs" / "audit.log"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._prev_hash = self._load_last_hash()

    def _load_last_hash(self) -> str:
        if not self.path.exists():
            return "0" * 64
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if lines:
                    last = json.loads(lines[-1])
                    return last.get("hash", "0" * 64)
        except Exception:
            pass
        return "0" * 64

    def log(
        self,
        action: str,
        target: str,
        value: str = "",
        operator: str = "ai-agent",
        success: bool = True,
        detail: str = "",
    ) -> dict:
        """记录一条审计日志（兼容 safety/audit.py 接口）"""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "target": target,
            "value": str(value),
            "operator": operator,
            "success": success,
            "detail": detail,
        }
        return self._write_entry(entry)

    def log_operation(self, operation: str, **kwargs) -> dict:
        """记录一条操作日志（兼容 tia-mcp/audit.py 接口）"""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            **kwargs,
        }
        return self._write_entry(entry)

    def _write_entry(self, entry: dict) -> dict:
        entry["prev_hash"] = self._prev_hash
        body = {k: v for k, v in entry.items() if k != "hash"}
        entry["hash"] = _compute_hash(body, self._prev_hash)

        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                f.flush()
        except Exception:
            pass

        self._prev_hash = entry["hash"]
        return entry

    def verify(self) -> bool:
        """验证日志链是否完整（检测篡改）"""
        if not self.path.exists():
            return True
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
            for i, line in enumerate(lines):
                entry = json.loads(line)
                expected = "0" * 64 if i == 0 else json.loads(lines[i - 1])["hash"]
                if entry.get("prev_hash") != expected:
                    return False
                body = {k: v for k, v in entry.items() if k != "hash"}
                if _compute_hash(body, entry["prev_hash"]) != entry["hash"]:
                    return False
            return True
        except Exception:
            return False

    def read_logs(self, operation: str = None, limit: int = 50) -> list:
        """读取最近的日志条目"""
        if not self.path.exists():
            return []
        entries = []
        with open(self.path, "r", encoding="utf-8") as f:
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


# ─── 全局单例 ───────────────────────────────────

_audit_logger: Optional[AuditLogger] = None

# 便捷单例引用（兼容: from mcp_common.audit import audit）
audit: AuditLogger = None  # type: ignore  # 首次访问时惰性初始化


def get_audit_logger(log_path: str = "") -> AuditLogger:
    """获取全局审计日志单例"""
    global _audit_logger, audit
    if _audit_logger is None:
        _audit_logger = AuditLogger(log_path)
        audit = _audit_logger
    return _audit_logger


def audit_log(operation: str, **kwargs) -> dict:
    """便捷函数：audit_log("operation_name", key1=val1, key2=val2)"""
    return get_audit_logger().log_operation(operation, **kwargs)
