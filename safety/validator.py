"""写入安全校验器 — 加载互锁规则并强制执行"""

import re
import time
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from mcp_common.config import env_config

_logger = logging.getLogger(__name__)
_cfg = env_config()
_MAX_ERRORS = int(_cfg.get("safety_max_consecutive_errors", "3"))
_WRITE_CONFIRM = str(_cfg.get("safety_write_confirm", "true")).lower() in ("true", "1", "yes")

FORBIDDEN_PATTERNS = [
    r".*ESTOP.*", r".*EMERGENCY.*", r".*E_STOP.*",
    r".*SAFETY.*", r".*SAFE_.*", r".*S_ESTOP.*",
]

CONFIRM_PATTERNS = [
    r".*MOTOR.*", r".*PUMP.*", r".*VALVE.*",
    r".*ROBOT.*", r".*CONVEYOR.*", r".*HEATER.*", r".*PRESS.*",
]

RULES_FILE = Path(__file__).parent / "interlock-rules.yml"


@dataclass
class ValidationResult:
    allowed: bool
    reason: str
    needs_confirmation: bool = False


class WriteValidator:
    def __init__(self):
        self.consecutive_errors = 0
        self._rules: list[dict] = []
        self._last_write_time: dict[str, float] = {}
        self._load_interlock_rules()

    def _load_interlock_rules(self):
        """加载互锁规则文件"""
        if not RULES_FILE.exists():
            _logger.warning(f"互锁规则文件不存在: {RULES_FILE}")
            return
        try:
            data = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
            self._rules = data.get("write_rules", [])
            _logger.info(f"已加载 {len(self._rules)} 条互锁规则")
        except Exception as e:
            _logger.error(f"加载互锁规则失败: {e}")

    def _check_interlock_rules(self, tag_name: str, value: Any) -> ValidationResult | None:
        """检查互锁规则（max_value, min_value, cooldown 等）"""
        for rule in self._rules:
            if rule.get("target") == tag_name:
                # 数值范围检查
                try:
                    num_value = float(value)
                except (ValueError, TypeError):
                    return None

                max_val = rule.get("max_value")
                if max_val is not None and num_value > max_val:
                    self.consecutive_errors += 1
                    return ValidationResult(False, f"超出最大值限制: {num_value} > {max_val}")

                min_val = rule.get("min_value")
                if min_val is not None and num_value < min_val:
                    self.consecutive_errors += 1
                    return ValidationResult(False, f"低于最小值限制: {num_value} < {min_val}")

                # 冷却时间检查
                cooldown = rule.get("cooldown_seconds")
                if cooldown:
                    last_time = self._last_write_time.get(tag_name, 0)
                    elapsed = time.time() - last_time
                    if elapsed < cooldown:
                        return ValidationResult(
                            False,
                            f"冷却时间未到: 还需等待 {cooldown - elapsed:.1f}s"
                        )

                # 记录写入时间
                self._last_write_time[tag_name] = time.time()
                break
        return None

    def validate(self, tag_name: str, value, current_value=None) -> ValidationResult:
        tag_upper = tag_name.upper()

        # 1. 检查禁止写入的安全标签
        for pat in FORBIDDEN_PATTERNS:
            if re.match(pat, tag_upper):
                self.consecutive_errors += 1
                return ValidationResult(False, f"禁止写入安全标签: {tag_name}")

        # 2. 检查熔断状态
        if self.consecutive_errors >= _MAX_ERRORS:
            return ValidationResult(False, f"熔断: 连续 {self.consecutive_errors} 次异常，请人工介入重置")

        # 3. 检查互锁规则（max/min/cooldown）
        rule_result = self._check_interlock_rules(tag_name, value)
        if rule_result is not None:
            return rule_result

        # 4. 全局合理范围检查
        if isinstance(value, (int, float)) and abs(value) > 1_000_000:
            self.consecutive_errors += 1
            return ValidationResult(False, f"值 {value} 超出合理范围")

        # 5. 值跳变检测
        if (current_value is not None
                and isinstance(value, (int, float))
                and isinstance(current_value, (int, float))
                and abs(float(current_value)) > 0.001):
            if abs(float(value) - float(current_value)) > abs(float(current_value)) * 10:
                self.consecutive_errors += 1
                return ValidationResult(False, f"值跳变过大: {current_value} -> {value}")

        # 通过所有检查，重置连续错误计数
        needs = _WRITE_CONFIRM and any(
            re.match(p, tag_upper) for p in CONFIRM_PATTERNS
        )
        self.consecutive_errors = 0
        return ValidationResult(True, "OK", needs_confirmation=needs)


validator = WriteValidator()
