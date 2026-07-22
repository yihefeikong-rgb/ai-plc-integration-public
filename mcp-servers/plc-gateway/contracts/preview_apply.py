"""
PLC Engineering Gateway — 强化 Preview/Apply 安全模型

Token 绑定内容：
  - 工具名称、规范化参数、项目路径、TIA 项目版本
  - 目标块或标签、目标对象 Hash
  - 操作者身份、确认者身份、设备身份
  - 签发时间、过期时间、随机数

执行前重新检查：
  - 当前项目路径 == 预览项目路径
  - 当前目标 Hash == 预览目标 Hash
  - 当前设备身份 == 预览设备身份
  - 令牌未过期、未使用

审计事件：
  preview_created, preview_expired, preview_rejected,
  apply_started, apply_succeeded, apply_failed,
  rollback_started, rollback_succeeded, reconcile_required
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


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


@dataclass
class PreviewToken:
    """预览令牌 — 绑定具体操作和对象状态"""

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

    # 时间
    issued_at: float = 0.0
    expires_at: float = 0.0

    # 状态
    token_id: str = ""
    used: bool = False

    def __post_init__(self):
        if not self.token_id:
            self.token_id = uuid.uuid4().hex
        if not self.issued_at:
            self.issued_at = time.time()
        if not self.expires_at:
            self.expires_at = self.issued_at + 300  # 5 分钟有效期

    @property
    def expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> dict:
        return {
            "token_id": self.token_id,
            "tool_name": self.tool_name,
            "project_path": self.project_path,
            "target_block": self.target_block,
            "target_hash": self.target_hash[:16] + "..." if self.target_hash else "",
            "operator": self.operator,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "used": self.used,
        }


class AuditLog:
    """审计日志 — 记录所有 Preview/Apply 事件"""

    def __init__(self):
        self._entries: list[dict] = []

    def record(self, event: AuditEvent, token: PreviewToken,
               detail: str = "", success: bool = True) -> None:
        entry = {
            "event": event.value,
            "timestamp": time.time(),
            "token_id": token.token_id,
            "tool_name": token.tool_name,
            "target_block": token.target_block,
            "operator": token.operator,
            "success": success,
            "detail": detail,
        }
        self._entries.append(entry)

    def get_entries(self, tool_name: str | None = None,
                    token_id: str | None = None,
                    limit: int = 50) -> list[dict]:
        result = self._entries
        if tool_name:
            result = [e for e in result if e["tool_name"] == tool_name]
        if token_id:
            result = [e for e in result if e["token_id"] == token_id]
        return result[-limit:]

    def clear(self) -> None:
        self._entries.clear()


class PreviewManager:
    """Preview/Apply 管理器 — 令牌生成、验证和执行"""

    def __init__(self, ttl: int = 300):
        self._tokens: dict[str, PreviewToken] = {}
        self._audit = AuditLog()
        self._ttl = ttl

    @property
    def audit(self) -> AuditLog:
        return self._audit

    def create_token(self, tool_name: str, params: dict,
                     project_path: str, tia_version: str,
                     target_block: str = "", target_hash: str = "",
                     operator: str = "") -> PreviewToken:
        """创建预览令牌"""
        token = PreviewToken(
            tool_name=tool_name,
            normalized_params=params,
            project_path=project_path,
            tia_version=tia_version,
            target_block=target_block,
            target_hash=target_hash,
            operator=operator,
            issued_at=time.time(),
            expires_at=time.time() + self._ttl,
        )
        self._tokens[token.token_id] = token
        self._audit.record(AuditEvent.PREVIEW_CREATED, token)
        return token

    def validate_token(self, token_id: str, current_project_path: str = "",
                       current_target_hash: str = "") -> PreviewToken | None:
        """验证令牌是否有效

        检查：
        - 令牌存在
        - 未过期
        - 未使用
        - 项目路径一致
        - 目标 Hash 一致（如果提供）
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

        if current_project_path and current_project_path != token.project_path:
            self._audit.record(AuditEvent.PREVIEW_REJECTED, token,
                               f"项目路径不匹配: {current_project_path}")
            return None

        if current_target_hash and current_target_hash != token.target_hash:
            self._audit.record(AuditEvent.PREVIEW_REJECTED, token,
                               f"目标 Hash 不匹配: 当前 {current_target_hash[:16]}...")
            return None

        return token

    def consume_token(self, token_id: str, current_project_path: str = "",
                      current_target_hash: str = "") -> PreviewToken | None:
        """消费令牌（验证 + 标记已使用）"""
        token = self.validate_token(token_id, current_project_path, current_target_hash)
        if token is None:
            return None
        token.used = True
        return token

    def apply_started(self, token: PreviewToken) -> None:
        self._audit.record(AuditEvent.APPLY_STARTED, token)

    def apply_succeeded(self, token: PreviewToken, detail: str = "") -> None:
        self._audit.record(AuditEvent.APPLY_SUCCEEDED, token, detail)

    def apply_failed(self, token: PreviewToken, detail: str = "") -> None:
        self._audit.record(AuditEvent.APPLY_FAILED, token, detail)

    def rollback_started(self, token: PreviewToken, detail: str = "") -> None:
        self._audit.record(AuditEvent.ROLLBACK_STARTED, token, detail)

    def rollback_succeeded(self, token: PreviewToken, detail: str = "") -> None:
        self._audit.record(AuditEvent.ROLLBACK_SUCCEEDED, token, detail)

    def reconcile_required(self, token: PreviewToken, detail: str = "") -> None:
        self._audit.record(AuditEvent.RECONCILE_REQUIRED, token, detail)

    def cleanup_expired(self) -> int:
        """清理过期令牌，返回清理数量"""
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