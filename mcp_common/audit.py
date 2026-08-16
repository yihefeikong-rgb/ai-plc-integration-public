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
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional

if os.name == "nt":  # Windows 进程间文件锁
    import msvcrt

    def _lock_region(file_obj) -> None:
        file_obj.seek(0)
        msvcrt.locking(file_obj.fileno(), msvcrt.LK_LOCK, 1)

    def _unlock_region(file_obj) -> None:
        file_obj.seek(0)
        msvcrt.locking(file_obj.fileno(), msvcrt.LK_UNLCK, 1)
else:  # POSIX 进程间文件锁
    import fcntl

    def _lock_region(file_obj) -> None:
        fcntl.flock(file_obj.fileno(), fcntl.LOCK_EX)

    def _unlock_region(file_obj) -> None:
        fcntl.flock(file_obj.fileno(), fcntl.LOCK_UN)


class _InterProcessLock:
    """跨进程互斥锁（基于审计文件旁的 .lock 文件）。

    多个 MCP 子进程与后端进程会同时追加同一条审计链；没有跨进程
    互斥时，各进程按自己内存中的 prev_hash 续链，链必然分叉。
    """

    def __init__(self, lock_path: Path):
        self._lock_path = lock_path
        self._handle = None

    def __enter__(self):
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = open(self._lock_path, "a+b")
        _lock_region(self._handle)
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            _unlock_region(self._handle)
        finally:
            self._handle.close()
            self._handle = None


class AuditConfigurationError(RuntimeError):
    """审计配置不满足控制动作的 fail-closed 要求。"""


class AuditStorageError(RuntimeError):
    """审计存储不可写或不可用。"""


_PRODUCTION_VALUES = {"production", "prod"}
_SENSITIVE_KEY = re.compile(
    r"\b(?:api[_-]?key|token|secret|password|passwd|authorization|credential|private[_-]?key|confirmation[_-]?token)\b",
    re.IGNORECASE,
)
_SENSITIVE_VALUE = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password|passwd|authorization|credential|private[_-]?key)\s*([=:])\s*([^\n,;]+)"
)


def _is_production_environment() -> bool:
    """仅将显式生产环境视为必须使用持久审计密钥的控制环境。"""
    return any(
        os.environ.get(name, "").strip().lower() in _PRODUCTION_VALUES
        for name in ("AI_PLC_ENV", "CONTROL_ENV", "APP_ENV", "ENVIRONMENT")
    )


_ephemeral_key_warned = False


def _warn_ephemeral_key() -> None:
    """对随机临时 HMAC 密钥只告警一次（进程级），避免静默不可交叉验证。"""
    global _ephemeral_key_warned
    if _ephemeral_key_warned:
        return
    _ephemeral_key_warned = True
    print(
        "[audit] 警告: 未配置 AUDIT_HMAC_KEY，审计链使用随机临时密钥，"
        "仅当前进程内可验证；重启或多进程写入后 verify() 无法交叉验证。",
        file=sys.stderr,
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
    """把已验证凭据转换为不可逆审计主体，绝不记录原始令牌。

    注意：本函数只做单向指纹用于审计归属，本身不验证凭据；生产环境下
    主体有效性由 ensure_control_ready()/_ensure_production_actor() 的
    fail-closed 门保证，调用方必须在传入前完成真实凭据校验。
    namespace 仅允许安全字符，防止注入伪造主体前缀。
    """
    if not isinstance(token, str) or not token or not token.strip():
        return ""
    safe_namespace = re.sub(r"[^A-Za-z0-9_-]", "_", namespace) or "mcp"
    fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    return f"{safe_namespace}:{fingerprint}"


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
            _warn_ephemeral_key()
        self._prev_hash = self._load_last_hash()

    def _ensure_storage_writable(self) -> None:
        """在控制动作前验证审计文件可追加。"""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.flush()
        except OSError as exc:
            raise AuditStorageError(f"审计存储不可写: {exc}") from exc

    def _ensure_production_actor(self, actor: str, purpose: str) -> None:
        """生产环境审计写入的 fail-closed 主体门：持久密钥 + 已认证主体。"""
        if self._ephemeral_key:
            raise AuditConfigurationError(
                "生产控制环境缺少持久 AUDIT_HMAC_KEY，拒绝执行控制动作"
            )
        if not isinstance(actor, str) or not actor.strip() or actor in {"ai", "ai-agent"}:
            raise AuditConfigurationError(
                f"{purpose}必须携带已认证操作者身份，拒绝执行控制动作"
            )

    def ensure_control_ready(self, actor: str) -> None:
        """生产控制动作的审计前置条件；任一条件不满足即拒绝。"""
        if self.production or _is_production_environment():
            self._ensure_production_actor(actor, "生产控制动作")
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
        """读取链尾 hash（只读文件末尾，避免大日志全量加载）。

        链尾损坏（JSON 解析失败、缺少合法 hash 或崩溃残留半行）时
        fail-closed 抛 AuditStorageError，绝不静默回退零锚重起链——
        否则"截断旧链 + 重锚追加"的篡改会让 verify() 无法检出。
        单条日志超过 64KB 时自动扩大读取窗口直到解析出完整末行。
        """
        if not self.path.exists():
            return "0" * 64
        window = 65536
        last_error: Optional[Exception] = None
        with open(self.path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size == 0:
                return "0" * 64
            while True:
                read_from = max(0, size - window)
                f.seek(read_from)
                tail = f.read(size - read_from).decode("utf-8", errors="replace")
                lines = [l for l in tail.splitlines() if l.strip()]
                if not lines:
                    if read_from == 0:
                        # 非空文件但整个文件内无任何非空行：链尾已损坏
                        # （如日志被截断成空白/纯换行）。此时静默回退零锚
                        # 会让"截断旧链 + 重锚追加"的篡改逃过 verify()，
                        # 必须 fail-closed。
                        raise AuditStorageError(
                            f"审计日志链尾缺少任何合法条目，拒绝静默重锚: {self.path}"
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
                            f"审计日志链尾缺少合法 hash，拒绝静默重锚: {self.path}"
                        )
                    return entry_hash
                if read_from == 0:
                    break
                window *= 4
        raise AuditStorageError(
            "审计日志链尾损坏，拒绝静默重锚续链: "
            f"{self.path}"
            + (f"（最后错误: {last_error}）" if last_error else "")
        )

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
        if self.production or _is_production_environment():
            self._ensure_production_actor(operator, "生产控制动作")
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
        if self.production or _is_production_environment():
            self._ensure_production_actor(
                kwargs.get("actor") or kwargs.get("operator") or "",
                "生产控制动作",
            )
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            **kwargs,
        }
        return self._write_entry(entry)

    def _write_entry(self, entry: dict) -> dict:
        entry = _redact(entry)

        # 锁内重读链尾 + 追加：多进程并发写同一审计链时，
        # 每个进程的内存 prev_hash 都不可信，必须以文件中的链尾为准。
        # 可写性由锁内追加 open 校验（失败抛 AuditStorageError），
        # 不再重复 _ensure_storage_writable 的检查 open。
        lock_path = self.path.with_name(self.path.name + ".lock")
        with _InterProcessLock(lock_path):
            prev_hash = self._load_last_hash()
            entry["prev_hash"] = prev_hash
            body = {k: v for k, v in entry.items() if k != "hash"}
            entry["hash"] = _compute_hash(body, prev_hash, self._hmac_key)

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
        """验证日志链是否完整（检测篡改）。

        返回 False 表示链断裂、条目哈希不符或数据损坏，并打印具体原因；
        存储层故障（文件不可读）以 AuditStorageError 上抛，与"篡改"
        语义区分，不再把所有失败合并成裸 False。
        """
        if not self.path.exists():
            return True
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = f.read()
            lines = [l.strip() for l in raw.splitlines() if l.strip()]
        except OSError as exc:
            raise AuditStorageError(f"verify(): 审计日志不可读 {self.path}: {exc}") from exc
        if raw and not lines:
            # 文件非空但解析不出任何合法条目（如只剩空白/纯换行）：
            # 按链损坏处理，不得当作"空链验证通过"放过截断式篡改。
            print(
                f"[audit] verify(): 审计日志非空但无任何合法条目（疑似被截断/空白化），数据损坏: {self.path}",
                file=sys.stderr,
            )
            return False
        for i, line in enumerate(lines):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"[audit] verify(): 审计日志损坏（行 {i + 1}）: {exc}", file=sys.stderr)
                return False
            if not isinstance(entry, dict):
                print(f"[audit] verify(): 审计条目不是 JSON 对象（行 {i + 1}），数据损坏", file=sys.stderr)
                return False
            if i == 0:
                expected = "0" * 64
            else:
                try:
                    expected = json.loads(lines[i - 1])["hash"]
                except json.JSONDecodeError as exc:
                    print(f"[audit] verify(): 审计日志损坏（行 {i}）: {exc}", file=sys.stderr)
                    return False
            if entry.get("prev_hash") != expected:
                print(f"[audit] verify(): 审计链在行 {i + 1} 断裂（prev_hash 不匹配），疑似篡改", file=sys.stderr)
                return False
            entry_hash = entry.get("hash")
            if not isinstance(entry_hash, str) or len(entry_hash) != 64:
                print(f"[audit] verify(): 审计条目缺少合法 hash（行 {i + 1}），数据损坏", file=sys.stderr)
                return False
            body = {k: v for k, v in entry.items() if k != "hash"}
            if _compute_hash(body, entry.get("prev_hash", ""), self._hmac_key) != entry_hash:
                print(f"[audit] verify(): 条目哈希不匹配（行 {i + 1}），疑似篡改", file=sys.stderr)
                return False
        return True

    def read_logs(self, operation: str = None, limit: int = 50) -> list:
        """读取最近的日志条目（从文件尾部向前分块扫描，避免大日志全量加载）。

        跨分块边界被截断的日志行会先拼接为完整行再解析，避免整条审计条目
        被静默丢弃；损坏且拼接后仍无法解析的完整行打印告警后跳过。
        """
        if not self.path.exists():
            return []
        entries: list[dict[str, Any]] = []
        window = 65536
        broken = 0
        with open(self.path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            pos = size
            # carry: 分块边界处被截断的行尾（在更晚的分块中），
            # 等与更早分块中的行首拼接成完整行后再解析
            carry = ""
            while pos > 0 and len(entries) < limit:
                read_from = max(0, pos - window)
                f.seek(max(0, read_from - 1))
                first_line_clean = read_from == 0 or f.read(1) == b"\n"
                f.seek(read_from)
                chunk = f.read(pos - read_from).decode("utf-8", errors="replace")
                pos = read_from
                lines = chunk.splitlines()
                if carry:
                    # 本分块末行延续到更晚分块（跨块行），拼回完整行
                    if lines:
                        lines[-1] += carry
                    else:
                        lines = [carry]
                    carry = ""
                if not first_line_clean:
                    # 分块首行被更早分块截断（半行），暂存待拼回
                    carry = lines.pop(0) if lines else ""
                for line in reversed(lines):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        broken += 1
                        continue
                    if operation and entry.get("operation") != operation:
                        continue
                    entries.append(entry)
                    if len(entries) >= limit:
                        break
        if broken:
            print(
                f"[audit] read_logs(): {broken} 条审计条目损坏且无法解析，已跳过；"
                "审计链完整性请用 verify() 检查",
                file=sys.stderr,
            )
        # 逆序收集（链尾在前），反转回时间正序；只保留最近 limit 条
        return list(reversed(entries))


# ─── 全局单例（惰性初始化） ───────────────────────────────────

_audit_logger: Optional[AuditLogger] = None
# 单例创建的线程互斥：避免并发首调创建两个实例（各自随机临时密钥，
# 导致同一日志链无法交叉 verify()）
_audit_logger_lock = threading.Lock()


class _LazyAuditProxy:
    """惰性代理：首次访问属性时才创建 AuditLogger 实例。
    解决 `from mcp_common.audit import audit` 得到 None 的问题。
    """

    def _get_instance(self) -> AuditLogger:
        global _audit_logger
        with _audit_logger_lock:
            if _audit_logger is None:
                _audit_logger = AuditLogger()
            return _audit_logger

    def __getattr__(self, name: str):
        return getattr(self._get_instance(), name)


# 便捷单例引用（兼容: from mcp_common.audit import audit）
audit: AuditLogger = _LazyAuditProxy()  # type: ignore


def get_audit_logger(log_path: str = "") -> AuditLogger:
    """获取全局审计日志单例。

    首次调用以 log_path 初始化；单例已存在且 log_path 指向不同文件时
    告警（不再静默忽略，避免审计写错文件而无察觉）。
    """
    global _audit_logger
    with _audit_logger_lock:
        if _audit_logger is None:
            _audit_logger = AuditLogger(log_path)
            return _audit_logger
    if log_path and str(Path(log_path).resolve()) != str(_audit_logger.path.resolve()):
        print(
            f"[audit] 警告: 审计单例已存在，忽略 get_audit_logger({log_path!r})，"
            f"当前审计文件为 {_audit_logger.path}",
            file=sys.stderr,
        )
    return _audit_logger


def audit_log(operation: str, **kwargs) -> dict:
    """便捷函数：audit_log("operation_name", key1=val1, key2=val2)"""
    return get_audit_logger().log_operation(operation, **kwargs)


def read_logs(operation: str = None, limit: int = 50) -> list:
    """便捷函数：read_logs(operation="write", limit=50)"""
    return get_audit_logger().read_logs(operation=operation, limit=limit)
