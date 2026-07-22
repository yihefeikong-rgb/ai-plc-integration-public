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
  apply_started, apply_succeeded, apply_failed,
  rollback_started, rollback_succeeded, reconcile_required
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class AuditEvent(Enum):
    """审计事件类型"""
    PREVIEW_CREATED = "preview_created"
    PREVIEW_EXPIRED = "preview_expired"
    PREVIEW_REJECTED = "preview_rejected"
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

    def __init__(self, log_dir: str | Path | None = None, hmac_key: str = ""):
        self._entries: list[dict] = []
        self._log_dir = Path(log_dir) if log_dir else None
        self._hmac_key = hmac_key
        self._last_hash = ""

    def set_log_dir(self, log_dir: str | Path) -> None:
        self._log_dir = Path(log_dir)

    def set_hmac_key(self, key: str) -> None:
        self._hmac_key = key

    def _load_existing(self) -> None:
        """从日志文件加载现有条目"""
        if not self._log_dir:
            return
        log_file = self._log_dir / "audit.jsonl"
        if not log_file.exists():
            return
        self._entries = []
        for line in log_file.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                entry = json.loads(line)
                self._entries.append(entry)
                self._last_hash = entry.get("chain_hash", "")

    def _compute_chain_hash(self, entry: dict) -> str:
        """计算链式哈希（当前条目 + 上一个哈希）"""
        payload = json.dumps(entry, sort_keys=True, ensure_ascii=False) + self._last_hash
        if self._hmac_key:
            return hmac.new(
                self._hmac_key.encode("utf-8"),
                payload.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _persist(self, entry: dict) -> None:
        """持久化审计条目到 JSON Lines 文件"""
        if not self._log_dir:
            return
        self._log_dir.mkdir(parents=True, exist_ok=True)
        log_file = self._log_dir / "audit.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def record(self, event: AuditEvent, token: PreviewToken,
               detail: str = "", success: bool = True) -> None:
        entry = {
            "event": event.value,
            "timestamp": time.time(),
            "token_id": token.token_id,
            "tool_name": token.tool_name,
            "target_block": token.target_block,
            "operator": token.operator,
            "confirmer": token.confirmer,
            "device_id": token.device_id,
            "success": success,
            "detail": detail,
        }
        # 计算链式哈希
        entry["chain_hash"] = self._compute_chain_hash(entry)
        self._last_hash = entry["chain_hash"]

        self._entries.append(entry)
        self._persist(entry)

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
        """验证审计链完整性，返回损坏的条目列表"""
        if not self._entries:
            return []
        prev_hash = ""
        broken = []
        for i, entry in enumerate(self._entries):
            chain_hash = entry.get("chain_hash", "")
            # 重建 hash
            entry_no_hash = {k: v for k, v in entry.items() if k != "chain_hash"}
            payload = json.dumps(entry_no_hash, sort_keys=True, ensure_ascii=False) + prev_hash
            if self._hmac_key:
                expected = hmac.new(
                    self._hmac_key.encode("utf-8"),
                    payload.encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest()
            else:
                expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if chain_hash != expected:
                broken.append({"index": i, "entry": entry, "expected": expected})
            prev_hash = chain_hash
        return broken

    def clear(self) -> None:
        self._entries.clear()
        self._last_hash = ""


class PreviewManager:
    """Preview/Apply 管理器 — 令牌生成、验证和执行（HMAC 签名 + 原子操作）"""

    def __init__(self, ttl: int = 300, secret_key: str = ""):
        self._tokens: dict[str, PreviewToken] = {}
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
        """消费令牌（验证 + 标记已使用）"""
        token = self.validate_token(
            token_id, current_project_path,
            current_target_hash, current_device_id,
        )
        if token is None:
            return None
        token.used = True
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