"""写入安全校验器 — 加载互锁规则并强制执行"""

import math
import re
import threading
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
    needs_confirmation: bool = False  # True=需要双人确认


class WriteValidator:
    def __init__(self):
        self._lock = threading.RLock()
        self.consecutive_errors = 0
        self._rules: list[dict] = []
        self._s7_write_addresses: dict[str, dict[str, str]] = {}
        self._last_write_time: dict[str, float] = {}
        self._bit_reader = None
        self._load_interlock_rules()

    def set_bit_reader(self, reader_fn):
        """注册 PLC 位读取回调（用于 require_bits 检查）

        Args:
            reader_fn: callable(address: str) -> bool | None
                       返回 True/False 表示位状态，None 表示读取失败
        """
        self._bit_reader = reader_fn

    def reset_fuse(self):
        """重置熔断计数器（调用方必须先消费一次性人工确认令牌）"""
        with self._lock:
            _logger.warning("熔断计数器已重置（需已消费人工确认令牌）")
            self.consecutive_errors = 0

    def _load_interlock_rules(self):
        """加载互锁规则文件"""
        if not RULES_FILE.exists():
            _logger.warning(f"互锁规则文件不存在: {RULES_FILE}")
            return
        try:
            data = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8")) or {}
            self._rules = data.get("write_rules", [])
            raw_addresses = data.get("s7_write_addresses", {})
            if not isinstance(raw_addresses, dict):
                raise ValueError("s7_write_addresses 必须是映射")
            self._s7_write_addresses = {}
            for address, mapping in raw_addresses.items():
                if not isinstance(mapping, dict):
                    raise ValueError(f"S7 地址映射格式无效: {address}")
                target = mapping.get("target")
                value_type = mapping.get("type")
                if not isinstance(target, str) or not target:
                    raise ValueError(f"S7 地址映射缺少 target: {address}")
                if value_type not in {"bool", "uint8", "int16", "float32"}:
                    raise ValueError(f"S7 地址映射类型无效: {address}")
                normalized = self._normalize_s7_address(address)
                self._s7_write_addresses[normalized] = {
                    "target": target,
                    "type": value_type,
                }
            _logger.info(f"已加载 {len(self._rules)} 条互锁规则")
        except Exception as e:
            _logger.error(f"加载互锁规则失败: {e}")

    @staticmethod
    def _normalize_s7_address(address: str) -> str:
        if not isinstance(address, str):
            raise ValueError("S7 地址必须是字符串")
        normalized = "".join(address.upper().split())
        if not normalized:
            raise ValueError("S7 地址不能为空")
        return normalized

    def resolve_s7_write_address(self, address: str) -> dict[str, str] | None:
        """返回原始地址对应的安全语义；未显式配置时拒绝写入。"""
        try:
            normalized = self._normalize_s7_address(address)
        except ValueError:
            return None
        mapping = self._s7_write_addresses.get(normalized)
        return dict(mapping) if mapping else None

    def _check_interlock_rules(self, tag_name: str, value: Any) -> ValidationResult | None:
        """检查互锁规则（require_bits, max_value, min_value, cooldown）"""
        for rule in self._rules:
            if rule.get("target") == tag_name:
                # require_bits 检查（安全前置条件）
                require_bits = rule.get("require_bits")
                if require_bits:
                    if self._bit_reader is None:
                        _logger.warning(f"require_bits 定义了但无 bit_reader: {require_bits}")
                        self.consecutive_errors += 1
                        return ValidationResult(
                            False,
                            f"安全前置条件无法验证（未注册 bit_reader）: {require_bits}"
                        )
                    for bit_addr in require_bits:
                        bit_val = self._bit_reader(bit_addr)
                        if bit_val is None:
                            self.consecutive_errors += 1
                            return ValidationResult(
                                False,
                                f"安全位读取失败: {bit_addr}（通信异常，拒绝写入）"
                            )
                        if not bit_val:
                            self.consecutive_errors += 1
                            return ValidationResult(
                                False,
                                f"安全前置条件不满足: {bit_addr} = FALSE（急停/安全回路未就绪）"
                            )

                # 数值范围检查
                try:
                    num_value = float(value)
                except (ValueError, TypeError):
                    return None
                if not math.isfinite(num_value):
                    self.consecutive_errors += 1
                    return ValidationResult(False, f"值必须是有限数值: {value}")

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
        with self._lock:
            return self._validate_locked(tag_name, value, current_value)

    def _validate_locked(self, tag_name: str, value, current_value=None) -> ValidationResult:
        tag_upper = str(tag_name).upper()

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
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            numeric_value = float(value)
            if not math.isfinite(numeric_value):
                self.consecutive_errors += 1
                return ValidationResult(False, f"值必须是有限数值: {value}")
            if abs(numeric_value) > 1_000_000:
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
