"""
统一安全拦截点 — 封装 safety.validator + safety.shadow_simulator。

所有写入操作必须经过此安全门，确保统一的安全策略执行。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from safety.validator import WriteValidator, ValidationResult
from safety.shadow_simulator import PreWriteChecker, ShadowResult
from safety.audit import audit

_logger = logging.getLogger(__name__)


@dataclass
class SafetyResult:
    """安全门检查结果，合并 validator + shadow_sim + audit 三阶段"""
    allowed: bool
    reason: str = ""
    needs_confirmation: bool = False
    shadow_result: ShadowResult | None = None
    validation_result: ValidationResult | None = None
    audit_id: str = ""
    warnings: list[str] = field(default_factory=list)


class SafetyGate:
    """统一安全拦截点。

    封装了项目的安全基础设施：
    1. WriteValidator — 互锁规则检查（禁止标签/数值范围/冷却时间）
    2. PreWriteChecker — 影子仿真（静态安全/变化率检测）
    3. AuditLogger — 审计日志注入

    使用方式:
        gate = SafetyGate()
        result = gate.check_write("DB1.MotorSpeed", 1500, operator="ai")
        if result.allowed:
            # 执行实际写入
            pass
    """

    def __init__(self, *, register_bit_reader: bool = True):
        self._validator = WriteValidator()
        self._shadow = PreWriteChecker()

    def set_bit_reader(self, reader_fn):
        """注册 PLC 位读取回调（用于 require_bits 互锁检查）"""
        self._validator.set_bit_reader(reader_fn)

    def _run_shadow_check(
        self, tag_name: str, value: Any, current_value: Any = None
    ) -> ShadowResult:
        """同步执行影子仿真检查（封装异步 simulate_write）"""
        try:
            loop = asyncio.get_running_loop()
            # 如果已有运行中的事件循环，无法直接 run_until_complete
            # 退化为同步的静态检查（跳过 asyncio.sleep）
            return self._shadow_sync_fallback(tag_name, value, current_value)
        except RuntimeError:
            # 没有运行中的事件循环，创建一个新的来运行
            return asyncio.run(
                self._shadow.simulate_write(tag_name, value, current_value)
            )

    def _shadow_sync_fallback(
        self, tag_name: str, value: Any, current_value: Any = None
    ) -> ShadowResult:
        """同步回退：执行影子仿真的静态检查部分（跳过异步延迟）"""
        # 1. 禁止标签检查
        if self._shadow._check_forbidden(tag_name):
            return ShadowResult(
                safe=False,
                reason=f"禁止写入安全标签: {tag_name}",
                predicted_value=current_value,
            )

        # 2. 值范围检查
        warnings: list[str] = []
        warnings.extend(self._shadow._check_value_bounds(value))

        # 3. 变化率检查
        warnings.extend(self._shadow._check_change_rate(tag_name, value))

        if warnings:
            return ShadowResult(
                safe=False,
                reason="; ".join(warnings),
                predicted_value=current_value,
                warnings=warnings,
            )

        return ShadowResult(
            safe=True,
            reason="shadow check passed (sync fallback)",
            predicted_value=value,
            warnings=warnings,
        )

    def check_write(
        self,
        tag_name: str,
        value: Any,
        *,
        operator: str = "ai",
        current_value: Any = None,
    ) -> SafetyResult:
        """对所有写入操作执行安全检查。

        执行顺序: validator → shadow_sim → audit

        Args:
            tag_name: PLC 标签名（如 "DB1.MotorSpeed"）
            value: 待写入的值
            operator: 操作者标识（"ai" / "human" / "system"）
            current_value: 当前值（可选，用于影子仿真）

        Returns:
            SafetyResult — allowed=True 表示可以执行写入
        """
        warnings: list[str] = []

        # 1. 互锁规则检查（禁止标签/数值范围/冷却时间）
        v_result = self._validator.validate(tag_name, value, current_value)
        if not v_result.allowed:
            audit.log(
                "write_rejected",
                tag_name,
                str(value),
                operator=operator,
                success=False,
                detail=v_result.reason,
            )
            return SafetyResult(
                allowed=False,
                reason=v_result.reason,
                needs_confirmation=v_result.needs_confirmation,
                validation_result=v_result,
                warnings=warnings,
            )

        # 2. 影子仿真检查（静态安全/变化率）
        s_result = self._run_shadow_check(tag_name, value, current_value)
        if not s_result.safe:
            audit.log(
                "write_rejected",
                tag_name,
                str(value),
                operator=operator,
                success=False,
                detail=s_result.reason,
            )
            return SafetyResult(
                allowed=False,
                reason=s_result.reason,
                shadow_result=s_result,
                validation_result=v_result,
                warnings=warnings + s_result.warnings,
            )

        # 3. 审计日志
        audit_entry = audit.log(
            "write_approved",
            tag_name,
            str(value),
            operator=operator,
        )
        audit_id = audit_entry.get("hash", "") if isinstance(audit_entry, dict) else ""

        return SafetyResult(
            allowed=True,
            reason="安全检查通过",
            needs_confirmation=v_result.needs_confirmation,
            shadow_result=s_result,
            validation_result=v_result,
            audit_id=audit_id,
            warnings=warnings + s_result.warnings,
        )

    def is_forbidden_tag(self, tag_name: str) -> bool:
        """检查标签是否属于禁止操作的安全标签"""
        result = self._validator.validate(tag_name, None)
        return not result.allowed

    def reset_fuse(self):
        """重置熔断计数器（需要双人确认后调用）"""
        self._validator.reset_fuse()


# 全局单例
_gate = SafetyGate()


def get_safety_gate() -> SafetyGate:
    """获取全局安全门单例"""
    return _gate