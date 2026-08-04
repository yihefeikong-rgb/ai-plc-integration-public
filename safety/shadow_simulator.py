"""
写入前置检查器（PreWriteChecker）— AI 写入前的静态安全检查。

注意: 本模块执行的是静态规则检查（禁止标签、数值范围、变化率），
并非真正的 PLC 影子仿真（不模拟 PLC 扫描周期或逻辑执行）。
真正的互锁条件检查（require_bits）在 safety.validator 中实现。

用法:
    from safety.shadow_simulator import shadow_sim

    result = await shadow_sim.simulate_write("DB1.MotorSpeed", 1500)
    if result.safe:
        # 执行真实写入
    else:
        print(f"[预检查] 拒绝: {result.reason}")
"""

from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

_logger = logging.getLogger(__name__)

# 仅在 safety.validator 导入失败时使用的回退禁止标签列表。
# 必须与 safety.validator.FORBIDDEN_PATTERNS 保持同步：任一处的增删都要同步另一处。
_FALLBACK_FORBIDDEN_PATTERNS = [
    r".*ESTOP.*", r".*EMERGENCY.*", r".*E_STOP.*",
    r".*SAFETY.*", r".*SAFE_.*", r".*S_ESTOP.*",
]


@dataclass
class ShadowResult:
    safe: bool
    reason: str = ""
    predicted_value: Any = None
    warnings: list[str] = field(default_factory=list)


class PreWriteChecker:
    """写入前置检查器（原 ShadowSimulator）

    在 AI 写入前执行静态安全检查：
    - 写入值是否在合理范围内
    - 标签是否属于禁止写入列表
    - 写入前后变化是否剧烈（变化率检测）

    注: 不模拟 PLC 逻辑执行，仅做数值级别安全检查。
    """

    def __init__(self):
        # 保存最后 N 个写入值用于变化检测
        self._history: dict[str, list[float | int]] = {}
        self._max_history = 5
        # tag 键数量上限（防止长时间运行导致键无限增长）
        self._max_history_tags = 256

        # 安全标签列表（不可写入）
        self._safe_tags: list[str] = []

        # 加载安全标签配置
        self._load_safe_tags()

    def _load_safe_tags(self):
        """从安全配置文件加载禁止写入的标签

        若 safety.validator 导入失败（依赖缺失、模块级配置解析异常等），
        降级到内置硬编码禁止标签列表并记录告警，避免禁止写入保护静默降级。
        """
        try:
            from safety.validator import FORBIDDEN_PATTERNS
            self._forbidden_patterns = FORBIDDEN_PATTERNS
        except Exception:
            # 必须捕获任意导入期异常而非仅 ImportError：safety.validator 在
            # 模块级执行 env_config() 与 int(...)（validator.py:16-17），环境
            # 变量为非数值时导入即抛 ValueError。只捕获 ImportError 会让本
            # 模块整体不可导入，内置禁止列表降级不生效（fail-closed 失效）。
            _logger.warning(
                "safety.validator 导入失败，禁止写入标签降级为内置硬编码列表",
                exc_info=True,
            )
            self._forbidden_patterns = list(_FALLBACK_FORBIDDEN_PATTERNS)

    def _check_forbidden(self, tag: str) -> bool:
        """检查标签是否属于禁止写入的安全标签"""
        import re
        tag_upper = tag.upper()
        for pat in self._forbidden_patterns:
            if re.match(pat, tag_upper):
                return True
        return False

    def _check_value_bounds(self, value: Any) -> list[str]:
        """检查值是否在合理范围内"""
        warnings = []
        if isinstance(value, (int, float)):
            if abs(value) > 1_000_000:
                warnings.append(f"值 {value} 超出合理范围（超过 1,000,000）")
            if isinstance(value, float) and value != value:  # NaN
                warnings.append("值为 NaN")
        return warnings

    def _check_change_rate(
        self, tag: str, value: Any, *, record_history: bool = True
    ) -> list[str]:
        """检查写入值相比历史值的变化率是否剧烈

        Args:
            tag: 标签名
            value: 要写入的值
            record_history: 本次检查通过时是否把值记入历史。被拒
                （超界/跳变）的写入值不得污染历史基线——否则会误拒
                后续合法写入，或被拒值成为基线后掩盖真实跳变。
        """
        warnings = []
        if not isinstance(value, (int, float)):
            return warnings

        history = self._history.get(tag)
        if history:
            prev = history[-1]
            if prev != 0 and abs(prev) > 0.001:
                ratio = abs(value - prev) / abs(prev)
                if ratio > 10:
                    warnings.append(
                        f"值跳变过大: {prev} -> {value} (变化率 {ratio:.1f}x)"
                    )

        if record_history and not warnings:
            if tag not in self._history:
                # tag 键数量上限：超过后淘汰最久未写入的键，防止长期运行内存增长
                if len(self._history) >= self._max_history_tags:
                    self._history.pop(next(iter(self._history)))
                self._history[tag] = []
            else:
                # 移动到字典末尾，使淘汰顺序接近 LRU
                self._history[tag] = self._history.pop(tag)
            history = self._history[tag]
            history.append(value)
            if len(history) > self._max_history:
                del history[: len(history) - self._max_history]

        return warnings

    async def simulate_write(
        self, tag: str, value: Any, current_value: Any = None
    ) -> ShadowResult:
        """模拟写入指定标签，返回仿真验证结果

        Args:
            tag: 标签名（如 "DB1.MotorSpeed"）
            value: 要写入的值
            current_value: 当前值（可选）

        Returns:
            ShadowResult 对象
        """
        warnings = []

        # 1. 检查禁止写入的安全标签
        if self._check_forbidden(tag):
            return ShadowResult(
                safe=False,
                reason=f"禁止写入安全标签: {tag}",
                predicted_value=current_value,
            )

        # 2. 检查值范围
        warnings.extend(self._check_value_bounds(value))

        # 3. 检查变化率（范围检查未通过时禁止记录历史基线）
        warnings.extend(
            self._check_change_rate(tag, value, record_history=not warnings)
        )

        if warnings:
            return ShadowResult(
                safe=False,
                reason="; ".join(warnings),
                predicted_value=current_value,
                warnings=warnings,
            )

        return ShadowResult(
            safe=True,
            reason="仿真通过",
            predicted_value=value,
        )


# 全局单例（保持 shadow_sim 别名兼容现有调用方）
shadow_sim = PreWriteChecker()
ShadowSimulator = PreWriteChecker  # 向后兼容
