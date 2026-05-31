"""写入安全校验器"""

import re
from dataclasses import dataclass
from config.settings import settings

FORBIDDEN_PATTERNS = [
    r".*ESTOP.*", r".*EMERGENCY.*", r".*E_STOP.*",
    r".*SAFETY.*", r".*SAFE_.*", r".*S_ESTOP.*",
]

CONFIRM_PATTERNS = [
    r".*MOTOR.*", r".*PUMP.*", r".*VALVE.*",
    r".*ROBOT.*", r".*CONVEYOR.*", r".*HEATER.*", r".*PRESS.*",
]


@dataclass
class ValidationResult:
    allowed: bool
    reason: str
    needs_confirmation: bool = False


class WriteValidator:
    def __init__(self):
        self.consecutive_errors = 0

    def validate(self, tag_name: str, value, current_value=None) -> ValidationResult:
        tag_upper = tag_name.upper()

        for pat in FORBIDDEN_PATTERNS:
            if re.match(pat, tag_upper):
                self.consecutive_errors += 1
                return ValidationResult(False, f"禁止写入安全标签: {tag_name}")

        if self.consecutive_errors >= settings.safety_max_errors:
            return ValidationResult(False, f"熔断: 连续 {self.consecutive_errors} 次异常")

        if isinstance(value, (int, float)) and abs(value) > 1_000_000:
            return ValidationResult(False, f"值 {value} 超出合理范围")

        if (current_value is not None
                and isinstance(value, (int, float))
                and isinstance(current_value, (int, float))
                and abs(float(current_value)) > 0.001):
            if abs(float(value) - float(current_value)) > abs(float(current_value)) * 10:
                return ValidationResult(False, f"值跳变过大: {current_value} -> {value}")

        needs = settings.safety_write_confirm and any(
            re.match(p, tag_upper) for p in CONFIRM_PATTERNS
        )
        self.consecutive_errors = 0
        return ValidationResult(True, "OK", needs_confirmation=needs)


validator = WriteValidator()
