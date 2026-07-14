"""
统一审计日志模块 — 合并 safety/audit.py 和 tia-mcp/audit.py 的功能。

特性:
  - HMAC-SHA256 链式防篡改（密钥来自 AUDIT_HMAC_KEY 环境变量）
  - 灵活的 log() 方法，支持 operation/action 双命名
  - 从配置文件读取日志路径（来自 tia-mcp/audit.py）
  - 向后兼容的 audit_log() 便捷函数
  - 惰性初始化：import 时不创建文件，首次写入时才初始化

用法:
    from mcp_common.audit import audit

    audit.log("write", "DB1.Motor", "1500", operator="ai")
    audit.log_operation("create_ladder_block", block_name="MotorFwdRev", result="ok")
"""

import hmac
import json
import hashlib
import os
import re
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional


class AuditConfigurationError(RuntimeError):
    """审计配置不满足控制动作的 fail-closed 要求。"""


class AuditStorageError(RuntimeError):
    """审计存储不可写或不可用。"""


_PRODUCTION_VALUES = {"production", "prod"}
_SENSITIVE_KEY = re.compile(
    r"(?:api[_-]?key|token|secret|password|passwd|authorization|credential|private[_-]?key|confirmation[_-]?token)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password|passwd|authorization|credential|private[_-]?key)\s*([=:])\s*([^\s,;]+)"
)


def _is_production_environment() -> bool:
    """仅将显式生产环境视为必须使用持久审计密钥的控制环境。"""
    return any(
        os.environ.get(name, "").strip().lower() in _PRODUCTION_VALUES
        for name in ("AI_PLC_ENV", "CONTROL_ENV", "APP_ENV", "ENVIRONMENT")
    )


def _redact(value: Any, key: str = "") -> Any:
    """递归脱敏后再落盘，避免把请求令牌或密钥写入审计日志。"""
    if _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item, key) for item in value]
    if isinstance(value, str):
        return _SENSITIVE_VALUE.sub(r"\1\2[REDACTED]", value)
    return value


def authenticated_actor(token: str, namespace: str = "mcp") -> str:
    """把已验证凭据转换为不可逆审计主体，绝不记录原始令牌。"""
    if not isinstance(token, str) or not token:
        return ""
    fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    return f"{namespace}:{fingerprint}"


def _compute_hash(entry: dict, prev_hash: str, hmac_key: bytes) -> str:
    payload = json.dumps(entry, sort_keys=True) + prev_hash
    return hmac.new(hmac_key, payload.encode(), hashlib.sha256).hexdigest()


class AuditLogger:
    """不可篡改的审计日志（链式哈希 + JSON Lines）

    同时支持两种调用风格:
      1. logger.log("write", "tag", "value")            # 兼容 safety/audit.py
      2. logger.log_operation("import_scl", ...)         # 兼容 tia-mcp/audit.py
    """

    def __init__(
        self,
        log_path: str | Path = "",
        *,
        hmac_key: str | bytes | None = None,
        production: bool | None = None,
    ):
        if log_path:
            self.path = Path(log_path)
        else:
            self.path = Path(__file__).parent.parent / "logs" / "audit.log"
        self.production = _is_production_environment() if production is None else production
        configured_key = hmac_key if hmac_key is not None else os.environ.get("AUDIT_HMAC_KEY")
        if isinstance(configured_key, str):
            configured_key = configured_key.encode()
        if configured_key:
            self._hmac_key = configured_key
            self._ephemeral_key = False
        elif self.production:
            raise AuditConfigurationError(
                "生产控制环境必须配置 AUDIT_HMAC_KEY，拒绝执行控制动作"
            )
        else:
            # 开发/离线测试不再使用可预测的默认密钥。该临时密钥不能跨进程
            # 验证旧日志，因此生产环境始终必须显式配置持久密钥。
            self._hmac_key = os.urandom(32)
            self._ephemeral_key = True
        self._prev_hash = self._load_last_hash()

    def _ensure_storage_writable(self) -> None:
        """在控制动作前验证审计文件可追加。"""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.flush()
        except OSError as exc:
            raise AuditStorageError(f"审计存储不可写: {exc}") from exc

    def ensure_control_ready(self, actor: str) -> None:
        """生产控制动作的审计前置条件；任一条件不满足即拒绝。"""
        if self.production or _is_production_environment():
            if self._ephemeral_key:
                raise AuditConfigurationError(
                    "生产控制环境缺少持久 AUDIT_HMAC_KEY，拒绝执行控制动作"
                )
            if not isinstance(actor, str) or not actor.strip() or actor in {"ai", "ai-agent"}:
                raise AuditConfigurationError(
                    "生产控制动作必须携带已认证操作者身份，拒绝执行控制动作"
                )
        try:
            self._ensure_storage_writable()
        except AuditStorageError:
            raise
        except OSError as exc:
            raise AuditStorageError(f"审计存储不可写: {exc}") from exc

    def begin_control_operation(
        self,
        operation: str,
        target: str,
        actor: str,
        params: dict[str, Any] | None = None,
    ) -> dict:
        """在任何控制副作用前写入审计意图；失败即阻断调用方。"""
        self.ensure_control_ready(actor)
        return self.log_operation(
            "control_intent",
            control_operation=operation,
            actor=actor,
            target=target,
            params=params or {},
        )

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
        entry = _redact(entry)
        self._ensure_storage_writable()
        entry["prev_hash"] = self._prev_hash
        body = {k: v for k, v in entry.items() if k != "hash"}
        entry["hash"] = _compute_hash(body, self._prev_hash, self._hmac_key)

        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                f.flush()
        except OSError as e:
            print(f"[audit] 审计日志写入失败: {e}", file=sys.stderr)
            raise AuditStorageError(f"审计存储不可写: {e}") from e

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
                if _compute_hash(body, entry["prev_hash"], self._hmac_key) != entry["hash"]:
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


# ─── 全局单例（惰性初始化） ───────────────────────────────────

_audit_logger: Optional[AuditLogger] = None


class _LazyAuditProxy:
    """惰性代理：首次访问属性时才创建 AuditLogger 实例。
    解决 `from mcp_common.audit import audit` 得到 None 的问题。
    """

    def _get_instance(self) -> AuditLogger:
        global _audit_logger
        if _audit_logger is None:
            _audit_logger = AuditLogger()
        return _audit_logger

    def __getattr__(self, name: str):
        return getattr(self._get_instance(), name)


# 便捷单例引用（兼容: from mcp_common.audit import audit）
audit: AuditLogger = _LazyAuditProxy()  # type: ignore


def get_audit_logger(log_path: str = "") -> AuditLogger:
    """获取全局审计日志单例"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(log_path)
    return _audit_logger


def audit_log(operation: str, **kwargs) -> dict:
    """便捷函数：audit_log("operation_name", key1=val1, key2=val2)"""
    return get_audit_logger().log_operation(operation, **kwargs)


def read_logs(operation: str = None, limit: int = 50) -> list:
    """便捷函数：read_logs(operation="write", limit=50)"""
    return get_audit_logger().read_logs(operation=operation, limit=limit)
