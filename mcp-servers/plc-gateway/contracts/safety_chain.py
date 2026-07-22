"""
PLC Engineering Gateway — 安全链

所有写操作必须经过 Gateway 安全链：
  1. 唯一项目目标检查
  2. 操作者认证
  3. 风险等级判断
  4. 导出修改前快照
  5. Preview
  6. 状态 Hash
  7. 一次性确认
  8. 执行操作
  9. 编译
  10. 重新读取对象
  11. 审计
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from ..policy.risk_levels import (
    RiskLevel, is_default_disabled, requires_preview,
    requires_confirmation, requires_backup,
)
from ..contracts.preview_apply import PreviewManager, get_preview_manager


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
    """安全链 — 门控检查"""

    def __init__(self, config: dict | None = None):
        self._config = config or {}
        self._preview_manager: PreviewManager | None = None

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

    def check_preview(self, risk_level: RiskLevel, has_preview_token: bool) -> SafetyGateResult:
        """检查是否需要 Preview"""
        if requires_preview(risk_level) and not has_preview_token:
            return SafetyGateResult.block(
                f"风险等级 {risk_level.value} 的操作必须经过 Preview")
        return SafetyGateResult.allow()

    def check_confirmation(self, risk_level: RiskLevel, confirmed: bool) -> SafetyGateResult:
        """检查是否需要人工确认"""
        if requires_confirmation(risk_level) and not confirmed:
            return SafetyGateResult.block(
                f"风险等级 {risk_level.value} 的操作必须人工确认")
        return SafetyGateResult.allow()

    def check_all(self, project_path: str, configured_project: str,
                  risk_level: RiskLevel, has_preview: bool = False,
                  confirmed: bool = False) -> SafetyGateResult:
        """执行所有安全检查"""
        checks = [
            ("目标检查", self.check_target(project_path, configured_project)),
            ("风险等级", self.check_risk_level(risk_level)),
            ("Preview", self.check_preview(risk_level, has_preview)),
            ("确认", self.check_confirmation(risk_level, confirmed)),
        ]
        for name, result in checks:
            if not result.allowed:
                return result
        return SafetyGateResult.allow()


# ── 全局安全链实例 ──
_safety_chain = SafetyChain()


def get_safety_chain() -> SafetyChain:
    return _safety_chain