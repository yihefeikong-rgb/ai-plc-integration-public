"""
PLC Engineering Gateway — 安全链

所有写操作必须经过 Gateway 安全链：
  1. 唯一项目目标检查
  2. 操作者认证
  3. 风险等级判断
  4. 导出修改前快照
  5. Preview（生成预览令牌）
  6. 状态 Hash
  7. 一次性确认（消费确认令牌）
  8. 执行操作（原子提交）
  9. 编译
  10. 重新读取对象
  11. 审计（HMAC 链）

失败状态：
  FAILED_NO_SIDE_EFFECT — 失败但无副作用
  FAILED_ROLLED_BACK — 失败并已回滚
  RECONCILE_REQUIRED — 失败且需要人工介入
"""
from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from plc_gateway.policy.risk_levels import (
    RiskLevel, is_default_disabled, requires_preview,
    requires_confirmation, requires_backup,
)
from plc_gateway.contracts.preview_apply import (
    PreviewManager, get_preview_manager, PreviewToken,
    ApplyFailureState, AuditEvent,
)


class SafetyGateResult:
    """安全闸检查结果"""
    def __init__(self, allowed: bool, reason: str = "", blocked: bool = False):
        self.allowed = allowed
        self.reason = reason
        self.blocked = blocked

    @classmethod
    def allow(cls) -> "SafetyGateResult":
        return cls(allowed=True)

    @classmethod
    def block(cls, reason: str) -> "SafetyGateResult":
        return cls(allowed=False, reason=reason, blocked=True)


class SafetyChain:
    """安全链 — 门控检查 + 原子 Apply"""

    def __init__(self, config: dict | None = None):
        self._config = config or {}
        self._preview_manager: PreviewManager | None = None
        self._secret_key = self._config.get("secret_key", "")

    def set_preview_manager(self, mgr: PreviewManager) -> None:
        self._preview_manager = mgr

    @property
    def preview_manager(self) -> PreviewManager:
        if self._preview_manager is None:
            self._preview_manager = get_preview_manager()
        return self._preview_manager

    def check_target(self, project_path: str, configured_project: str) -> SafetyGateResult:
        """检查项目目标是否匹配"""
        import os
        if not os.path.normcase(os.path.normpath(project_path)) == \
               os.path.normcase(os.path.normpath(configured_project)):
            return SafetyGateResult.block(
                f"目标项目不匹配: {project_path} != {configured_project}")
        return SafetyGateResult.allow()

    def check_risk_level(self, risk_level: RiskLevel) -> SafetyGateResult:
        """检查风险等级是否允许"""
        if is_default_disabled(risk_level):
            return SafetyGateResult.block(
                f"风险等级 {risk_level.value} 的操作默认禁用，需手动启用")
        return SafetyGateResult.allow()

    def check_preview_token(self, token_id: str, project_path: str = "",
                            target_hash: str = "", device_id: str = "") -> SafetyGateResult:
        """检查预览令牌是否有效"""
        mgr = self.preview_manager
        token = mgr.validate_token(token_id, project_path, target_hash, device_id)
        if token is None:
            return SafetyGateResult.block("预览令牌无效或已过期")
        return SafetyGateResult.allow()

    def check_confirmation(self, confirmed: bool = False,
                           confirmation_token: str = "") -> SafetyGateResult:
        """检查确认（支持传统 confirmed 布尔值和确认令牌）"""
        if confirmation_token:
            # 验证确认令牌
            token = self.preview_manager.validate_token(confirmation_token)
            if token is None:
                return SafetyGateResult.block("确认令牌无效")
            return SafetyGateResult.allow()
        if not confirmed:
            return SafetyGateResult.block("操作必须人工确认")
        return SafetyGateResult.allow()

    def check_all(self, project_path: str, configured_project: str,
                  risk_level: RiskLevel, preview_token: str = "",
                  confirmed: bool = False,
                  confirmation_token: str = "",
                  target_hash: str = "",
                  device_id: str = "") -> SafetyGateResult:
        """执行所有安全检查"""
        checks = [
            ("目标检查", self.check_target(project_path, configured_project)),
            ("风险等级", self.check_risk_level(risk_level)),
        ]

        # 需要 Preview 的操作必须提供预览令牌
        if requires_preview(risk_level):
            if not preview_token:
                return SafetyGateResult.block(
                    f"风险等级 {risk_level.value} 的操作必须提供预览令牌")
            checks.append(("预览令牌", self.check_preview_token(
                preview_token, project_path, target_hash, device_id)))

        # 需要确认的操作必须确认
        if requires_confirmation(risk_level):
            result = self.check_confirmation(confirmed, confirmation_token)
            if not result.allowed:
                return result

        for name, result in checks:
            if not result.allowed:
                return result
        return SafetyGateResult.allow()

    def atomic_apply(self, token: PreviewToken,
                     apply_fn: Callable[[], tuple[bool, str, ApplyFailureState]],
                     rollback_fn: Callable[[], bool] | None = None) -> dict:
        """原子 Apply 操作

        Args:
            token: 预览令牌
            apply_fn: 执行函数，返回 (success, detail, failure_state)
            rollback_fn: 回滚函数（可选）

        Returns:
            操作结果字典
        """
        mgr = self.preview_manager

        # 1. 标记开始
        mgr.apply_started(token)

        # 2. 消费令牌（原子操作前最后验证）
        consumed = mgr.consume_token(
            token.token_id, token.project_path,
            token.target_hash, token.device_id,
        )
        if consumed is None:
            mgr.apply_failed(token, "令牌消费失败（并发冲突或已过期）",
                             ApplyFailureState.RECONCILE_REQUIRED)
            return {"ok": False, "status": "reconcile_required",
                    "error": "令牌消费失败，可能需要人工介入"}

        # 3. 执行操作
        try:
            success, detail, failure_state = apply_fn()
        except Exception as e:
            # 尝试回滚
            if rollback_fn:
                try:
                    mgr.rollback_started(token, str(e))
                    if rollback_fn():
                        mgr.rollback_succeeded(token, str(e))
                    else:
                        mgr.reconcile_required(token, f"回滚失败: {e}")
                        return {"ok": False, "status": "reconcile_required",
                                "error": f"操作失败，回滚也失败: {e}"}
                except Exception:
                    mgr.reconcile_required(token, f"回滚异常: {e}")
                    return {"ok": False, "status": "reconcile_required",
                            "error": f"操作异常且回滚异常: {e}"}

            mgr.apply_failed(token, str(e), ApplyFailureState.FAILED_NO_SIDE_EFFECT)
            return {"ok": False, "status": "failed", "error": str(e)}

        if success:
            mgr.apply_succeeded(token, detail)
            return {"ok": True, "status": "success", "detail": detail}
        else:
            mgr.apply_failed(token, detail, failure_state)
            return {"ok": False, "status": failure_state.value, "error": detail}


# ── 全局安全链实例 ──
_safety_chain = SafetyChain()


def get_safety_chain() -> SafetyChain:
    return _safety_chain
