"""
PLC Engineering Gateway — 强化 Preview/Apply 安全模型

Token 绑定内容：
  - 工具名称、规范化参数、项目路径、TIA 项目版本
  - 目标块或标签、目标对象 Hash
  - 操作者身份、确认者身份、设备身份
  - 签发时间、过期时间、随机数、HMAC 签名

执行前重新检查：
  - 当前项目路径 == 预览项目路径
  - 当前目标 Hash == 预览目标 Hash
  - 当前设备身份 == 预览设备身份
  - 令牌未过期、未使用、签名有效

审计事件（持久化 HMAC 链）：
  preview_created, preview_expired, preview_rejected,
  token_consumed,
  apply_started, apply_succeeded, apply_failed,
  rollback_started, rollback_succeeded, reconcile_required
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

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
    """跨进程互斥锁（审计文件旁的 .lock 文件，模式同 mcp_common/audit.py）。

    多个 Gateway 进程会追加同一条审计链；没有跨进程互斥时，各进程按
    自己内存中的 _last_hash 续链，并发写必然导致链分叉。
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


# normalized_params 中的凭据类字段不得进入审计链（模式同 mcp_common/audit.py）
_SENSITIVE_KEY = re.compile(
    r"\b(?:api[_-]?key|token|secret|password|passwd|authorization|credential|private[_-]?key)\b",
    re.IGNORECASE,
)


def _redact_params(value: Any) -> Any:
    """递归脱敏 normalized_params：凭据类键替换为 [REDACTED]"""
    if isinstance(value, dict):
        return {
            str(k): "[REDACTED]" if _SENSITIVE_KEY.search(str(k)) else _redact_params(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_params(item) for item in value]
    return value


class AuditEvent(Enum):
    """审计事件类型"""
    PREVIEW_CREATED = "preview_created"
    PREVIEW_EXPIRED = "preview_expired"
    PREVIEW_REJECTED = "preview_rejected"
    TOKEN_CONSUMED = "token_consumed"
    APPLY_STARTED = "apply_started"
    APPLY_SUCCEEDED = "apply_succeeded"
    APPLY_FAILED = "apply_failed"
    ROLLBACK_STARTED = "rollback_started"
    ROLLBACK_SUCCEEDED = "rollback_succeeded"
    RECONCILE_REQUIRED = "reconcile_required"


class ApplyFailureState(Enum):
    """Apply 失败状态"""
    FAILED_NO_SIDE_EFFECT = "failed_no_side_effect"
    FAILED_ROLLED_BACK = "failed_rolled_back"
    RECONCILE_REQUIRED = "reconcile_required"


@dataclass
class PreviewToken:
    """预览令牌 — 绑定具体操作和对象状态（HMAC 签名）"""

    # 工具信息
    tool_name: str
    normalized_params: dict

    # 项目绑定
    project_path: str
    tia_version: str

    # 目标绑定
    target_block: str = ""
    target_hash: str = ""

    # 操作者
    operator: str = ""
    confirmer: str = ""

    # 设备绑定
    device_id: str = ""

    # 时间
    issued_at: float = 0.0
    expires_at: float = 0.0

    # 状态
    token_id: str = ""
    used: bool = False

    # HMAC 签名
    signature: str = ""

    def __post_init__(self):
        if not self.token_id:
            self.token_id = uuid.uuid4().hex[:16]
        if not self.issued_at:
            self.issued_at = time.time()
        if not self.expires_at:
            self.expires_at = self.issued_at + 300  # 5 分钟有效期

    @property
    def expired(self) -> bool:
        return time.time() > self.expires_at

    def to_signing_payload(self) -> str:
        """生成用于 HMAC 签名的规范化字符串"""
        parts = [
            self.token_id,
            self.tool_name,
            json.dumps(self.normalized_params, sort_keys=True, ensure_ascii=False),
            self.project_path,
            self.tia_version,
            self.target_block,
            self.target_hash,
            self.operator,
            self.confirmer,
            self.device_id,
            f"{self.issued_at:.6f}",
            f"{self.expires_at:.6f}",
        ]
        return "|".join(parts)

    def sign(self, secret_key: str) -> None:
        """使用 HMAC-SHA256 签名"""
        payload = self.to_signing_payload()
        self.signature = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def verify_signature(self, secret_key: str) -> bool:
        """验证 HMAC 签名"""
        if not self.signature:
            return False
        expected = hmac.new(
            secret_key.encode("utf-8"),
            self.to_signing_payload().encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(self.signature, expected)

    def to_dict(self) -> dict:
        return {
            "token_id": self.token_id,
            "tool_name": self.tool_name,
            "project_path": self.project_path,
            "target_block": self.target_block,
            "target_hash": self.target_hash[:16] + "..." if self.target_hash else "",
            "operator": self.operator,
            "confirmer": self.confirmer,
            "device_id": self.device_id,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "used": self.used,
            "signature": self.signature[:16] + "..." if self.signature else "",
        }


class AuditLog:
    """审计日志 — 持久化 HMAC 链（JSON Lines + 链式哈希）"""

    # 内存只保留最近 N 条；全量历史始终落盘，重启后从磁盘接续链尾
    MAX_IN_MEMORY_ENTRIES = 1000

    def __init__(self, log_dir: str | Path | None = None, hmac_key: str = ""):
        self._entries: list[dict] = []
        self._log_dir = Path(log_dir) if log_dir else self._default_log_dir()
        # 未配置 HMAC 密钥时使用进程内临时密钥，绝不降级为可伪造的裸 SHA-256
        self._hmac_key = hmac_key or os.urandom(32).hex()
        self._last_hash = ""
        # record 的读改写（_last_hash + _persist 追加）必须互斥，
        # 否则并发写链分叉
        self._lock = threading.Lock()
        self._load_existing()

    @staticmethod
    def _default_log_dir() -> Path:
        """默认审计目录：PLC_GATEWAY_AUDIT_DIR 覆盖，否则项目 logs/plc-gateway"""
        env_dir = os.environ.get("PLC_GATEWAY_AUDIT_DIR")
        if env_dir:
            return Path(env_dir)
        return Path(__file__).resolve().parents[3] / "logs" / "plc-gateway"

    def set_log_dir(self, log_dir: str | Path) -> None:
        """切换审计目录并接续该目录已有链尾（HMAC 链跨重启连续）"""
        new_dir = Path(log_dir)
        if new_dir == self._log_dir:
            return
        self._log_dir = new_dir
        self._load_existing()

    def set_hmac_key(self, key: str) -> None:
        if key:
            self._hmac_key = key

    def _read_all_from_disk(self) -> list[dict]:
        """读取磁盘上的完整审计链条目（JSON Lines）"""
        log_file = self._log_dir / "audit.jsonl"
        if not log_file.exists():
            return []
        entries = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    def _load_existing(self) -> None:
        """从日志文件加载现有条目并接续链尾 hash（内存只保留最近窗口）"""
        try:
            entries = self._read_all_from_disk()
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"审计日志损坏，拒绝静默续链: {self._log_dir / 'audit.jsonl'}: {exc}"
            ) from exc
        self._entries = entries[-self.MAX_IN_MEMORY_ENTRIES:]
        self._last_hash = entries[-1].get("chain_hash", "") if entries else ""

    def _load_last_hash_from_disk(self) -> str:
        """只读文件尾部窗口取磁盘链尾 hash（record 锁内调用）。

        多进程并发写同一审计链时，本进程内存中的 _last_hash 不可信，
        必须以磁盘链尾为准续链（模式同 mcp_common/audit.py）。尾部
        存在崩溃残留半行时取窗口内最后一个可解析条目；文件非空但
        整个窗口解析不出合法链尾时 fail-closed 抛异常，拒绝静默重锚。
        """
        log_file = self._log_dir / "audit.jsonl"
        if not log_file.exists():
            return ""
        with open(log_file, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size == 0:
                return ""
            window = min(size, 65536)
            f.seek(size - window)
            tail = f.read(window).decode("utf-8", errors="replace")
        for line in reversed([l for l in tail.splitlines() if l.strip()]):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(entry, dict) and isinstance(entry.get("chain_hash"), str) \
                    and entry["chain_hash"]:
                return entry["chain_hash"]
        raise RuntimeError(
            f"审计日志尾部无合法链尾，拒绝静默重锚: {log_file}")

    def _compute_chain_hash(self, entry: dict) -> str:
        """计算链式哈希（当前条目 + 上一个哈希，HMAC-SHA256）"""
        payload = json.dumps(entry, sort_keys=True, ensure_ascii=False) + self._last_hash
        return hmac.new(
            self._hmac_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _persist(self, entry: dict) -> None:
        """持久化审计条目到 JSON Lines 文件（写入失败即阻断，fail-closed）"""
        self._log_dir.mkdir(parents=True, exist_ok=True)
        log_file = self._log_dir / "audit.jsonl"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            raise RuntimeError(f"审计日志写入失败: {log_file}: {exc}") from exc

    def record(self, event: AuditEvent, token: PreviewToken,
               detail: str = "", success: bool = True) -> None:
        entry = {
            "event": event.value,
            "timestamp": time.time(),
            "token_id": token.token_id,
            "tool_name": token.tool_name,
            # 操作载荷：实际写入的规范化参数（凭据类字段脱敏），
            # 让 TOKEN_CONSUMED / APPLY_* 审计条目可还原实际操作内容
            "params": _redact_params(token.normalized_params),
            "target_block": token.target_block,
            "operator": token.operator,
            "confirmer": token.confirmer,
            "device_id": token.device_id,
            "success": success,
            "detail": detail,
        }
        # 读改写 + 追加全程持锁：进程内 threading.Lock，跨进程文件锁。
        # 锁内以磁盘链尾为锚（多进程并发写时内存 _last_hash 不可信）。
        with self._lock:
            with _InterProcessLock(self._log_dir / "audit.jsonl.lock"):
                self._last_hash = self._load_last_hash_from_disk()
                entry["chain_hash"] = self._compute_chain_hash(entry)
                # 先落盘后更新内存：写入失败（fail-closed 抛出）时
                # 内存锚与条目窗口保持与磁盘一致
                self._persist(entry)
            self._last_hash = entry["chain_hash"]

            self._entries.append(entry)
            # 内存只保留最近窗口，防止长期运行无限增长（全量历史已在磁盘）
            if len(self._entries) > self.MAX_IN_MEMORY_ENTRIES:
                self._entries = self._entries[-self.MAX_IN_MEMORY_ENTRIES:]

    def get_entries(self, tool_name: str | None = None,
                    token_id: str | None = None,
                    limit: int = 50) -> list[dict]:
        result = self._entries
        if tool_name:
            result = [e for e in result if e["tool_name"] == tool_name]
        if token_id:
            result = [e for e in result if e["token_id"] == token_id]
        return result[-limit:]

    def verify_chain(self) -> list[dict]:
        """验证审计链完整性，返回损坏的条目列表

        以磁盘上的完整链为准（内存只保留最近窗口），
        避免裁剪内存条目导致链验证误报或漏报。
        损坏行（JSON 解析失败或非对象）作为损坏条目返回，不再上抛
        JSONDecodeError；损坏行之后的链连续性已不可证，跳过其后
        条目的 hash 复核（损坏行本身已计入报告）。
        """
        log_file = self._log_dir / "audit.jsonl"
        if not log_file.exists():
            return []
        entries: list[dict | None] = []
        broken: list[dict] = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as exc:
                    broken.append({
                        "index": len(entries),
                        "entry": None,
                        "line": line_no,
                        "error": f"损坏行（无法解析为 JSON）: {exc}",
                    })
                    entries.append(None)
                    continue
                if not isinstance(entry, dict):
                    broken.append({
                        "index": len(entries),
                        "entry": None,
                        "line": line_no,
                        "error": "损坏行（条目不是 JSON 对象）",
                    })
                    entries.append(None)
                    continue
                entries.append(entry)
        if not entries:
            return broken
        prev_hash = ""
        chain_interrupted = False
        for i, entry in enumerate(entries):
            if entry is None:
                chain_interrupted = True
                continue
            if chain_interrupted:
                # 损坏行之后的条目缺少可信 prev_hash，无法复核
                continue
            chain_hash = entry.get("chain_hash", "")
            # 重建 hash
            entry_no_hash = {k: v for k, v in entry.items() if k != "chain_hash"}
            payload = json.dumps(entry_no_hash, sort_keys=True, ensure_ascii=False) + prev_hash
            expected = hmac.new(
                self._hmac_key.encode("utf-8"),
                payload.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if chain_hash != expected:
                broken.append({"index": i, "entry": entry, "expected": expected})
            prev_hash = chain_hash
        return broken

    def clear(self) -> None:
        """清空审计链：内存锚与磁盘文件同步重置。

        只重置内存不清磁盘会让后续追加以空锚续写、与磁盘旧链断链，
        因此磁盘文件在跨进程锁内一并删除（删除失败即抛出，fail-closed）。
        """
        with self._lock:
            with _InterProcessLock(self._log_dir / "audit.jsonl.lock"):
                log_file = self._log_dir / "audit.jsonl"
                if log_file.exists():
                    log_file.unlink()
                self._entries.clear()
                self._last_hash = ""


class PreviewManager:
    """Preview/Apply 管理器 — 令牌生成、验证和执行（HMAC 签名 + 原子操作）"""

    def __init__(self, ttl: int = 300, secret_key: str = ""):
        self._tokens: dict[str, PreviewToken] = {}
        # 可重入锁：token.used 的读-改-写必须原子，防止并发消费同一确认令牌
        # 同时重放（TOCTOU），保证一次性消费/防重放语义 fail-closed。
        self._lock = threading.RLock()
        self._audit = AuditLog()
        self._ttl = ttl
        self._secret_key = secret_key

    def set_ttl(self, ttl: int) -> None:
        self._ttl = ttl

    def set_secret_key(self, key: str) -> None:
        self._secret_key = key
        self._audit.set_hmac_key(key)

    @property
    def audit(self) -> AuditLog:
        return self._audit

    def create_token(self, tool_name: str, params: dict,
                     project_path: str, tia_version: str,
                     target_block: str = "", target_hash: str = "",
                     operator: str = "", confirmer: str = "",
                     device_id: str = "") -> PreviewToken:
        """创建预览令牌（自动签名）"""
        with self._lock:
            token = PreviewToken(
                token_id=uuid.uuid4().hex[:16],
                tool_name=tool_name,
                normalized_params=params,
                project_path=project_path,
                tia_version=tia_version,
                target_block=target_block,
                target_hash=target_hash,
                operator=operator,
                confirmer=confirmer,
                device_id=device_id,
                issued_at=time.time(),
                expires_at=time.time() + self._ttl,
            )
            if self._secret_key:
                token.sign(self._secret_key)
            self._tokens[token.token_id] = token
            self._audit.record(AuditEvent.PREVIEW_CREATED, token)
            return token

    def validate_token(self, token_id: str, current_project_path: str = "",
                       current_target_hash: str = "",
                       current_device_id: str = "") -> PreviewToken | None:
        """验证令牌是否有效

        检查：
        - 令牌存在
        - 未过期
        - 未使用
        - HMAC 签名有效（如果配置了密钥）
        - 项目路径一致
        - 目标 Hash 一致（如果提供）
        - 设备 ID 一致（如果提供）
        """
        with self._lock:
            token = self._tokens.get(token_id)
            if token is None:
                return None

            if token.expired:
                self._audit.record(AuditEvent.PREVIEW_EXPIRED, token, "令牌已过期")
                self._tokens.pop(token_id, None)
                return None

            if token.used:
                self._audit.record(AuditEvent.PREVIEW_REJECTED, token, "令牌已使用")
                return None

            # HMAC 签名验证
            if self._secret_key and token.signature:
                if not token.verify_signature(self._secret_key):
                    self._audit.record(AuditEvent.PREVIEW_REJECTED, token, "HMAC 签名无效")
                    return None

            # "token 有绑定就必须验证"：token 自身记录了非空绑定
            # （project_path / target_hash / device_id）而调用方未提供
            # 对应当前值时，无法证明绑定一致，fail-closed 拒绝——
            # 不允许空参数静默跳过绑定校验
            if token.project_path and not current_project_path:
                self._audit.record(AuditEvent.PREVIEW_REJECTED, token,
                                   "令牌绑定了项目路径，但未提供当前项目路径以验证绑定")
                return None
            if token.target_hash and not current_target_hash:
                self._audit.record(AuditEvent.PREVIEW_REJECTED, token,
                                   "令牌绑定了目标 Hash，但未提供当前目标 Hash 以验证绑定")
                return None
            if token.device_id and not current_device_id:
                self._audit.record(AuditEvent.PREVIEW_REJECTED, token,
                                   "令牌绑定了设备 ID，但未提供当前设备 ID 以验证绑定")
                return None

            if current_project_path and current_project_path != token.project_path:
                self._audit.record(AuditEvent.PREVIEW_REJECTED, token,
                                   f"项目路径不匹配: {current_project_path}")
                return None

            if current_target_hash and current_target_hash != token.target_hash:
                self._audit.record(AuditEvent.PREVIEW_REJECTED, token,
                                   f"目标 Hash 不匹配: 当前 {current_target_hash[:16]}...")
                return None

            if current_device_id and current_device_id != token.device_id:
                self._audit.record(AuditEvent.PREVIEW_REJECTED, token,
                                   f"设备 ID 不匹配: {current_device_id}")
                return None

            return token

    def consume_token(self, token_id: str, current_project_path: str = "",
                      current_target_hash: str = "",
                      current_device_id: str = "") -> PreviewToken | None:
        """消费令牌（验证 + 标记已使用 + 审计一次性消费）"""
        # 整个“验证 + used 置位 + 审计”在同一把锁下执行，
        # 并发调用同一令牌时后到者必然读到 used=True 而被拒绝（防重放）。
        with self._lock:
            token = self.validate_token(
                token_id, current_project_path,
                current_target_hash, current_device_id,
            )
            if token is None:
                return None
            token.used = True
            self._audit.record(AuditEvent.TOKEN_CONSUMED, token, "令牌已一次性消费")
            return token

    def apply_started(self, token: PreviewToken) -> None:
        self._audit.record(AuditEvent.APPLY_STARTED, token)

    def apply_succeeded(self, token: PreviewToken, detail: str = "") -> None:
        self._audit.record(AuditEvent.APPLY_SUCCEEDED, token, detail)

    def apply_failed(self, token: PreviewToken, detail: str = "",
                     failure_state: ApplyFailureState = ApplyFailureState.FAILED_NO_SIDE_EFFECT) -> None:
        self._audit.record(AuditEvent.APPLY_FAILED, token,
                           f"{failure_state.value}: {detail}")

    def rollback_started(self, token: PreviewToken, detail: str = "") -> None:
        self._audit.record(AuditEvent.ROLLBACK_STARTED, token, detail)

    def rollback_succeeded(self, token: PreviewToken, detail: str = "") -> None:
        self._audit.record(AuditEvent.ROLLBACK_SUCCEEDED, token, detail)

    def reconcile_required(self, token: PreviewToken, detail: str = "") -> None:
        self._audit.record(AuditEvent.RECONCILE_REQUIRED, token, detail)

    def cleanup_expired(self) -> int:
        with self._lock:
            now = time.time()
            expired = [tid for tid, t in self._tokens.items()
                       if now > t.expires_at]
            for tid in expired:
                self._audit.record(AuditEvent.PREVIEW_EXPIRED,
                                   self._tokens[tid], "自动清理过期令牌")
                del self._tokens[tid]
            return len(expired)


# ── 全局实例 ──
_preview_manager = PreviewManager()


def get_preview_manager() -> PreviewManager:
    return _preview_manager