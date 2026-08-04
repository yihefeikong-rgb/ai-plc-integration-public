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


def _parse_max_errors(raw_value: Any) -> int:
    """解析 safety_max_consecutive_errors 配置。

    外部 env/.env 值不可信：非数字或非法数字一律 fail-closed 回退为 1
    （连续 1 次异常即熔断，最严格），并记录可读错误，避免模块级 int()
    崩溃拖垮全部 import 方。
    """
    try:
        value = int(raw_value)
    except (ValueError, TypeError):
        _logger.error(
            f"无效的 safety_max_consecutive_errors={raw_value!r}，"
            "fail-closed 回退为 1（连续 1 次异常即熔断）"
        )
        return 1
    if value < 1:
        _logger.error(
            f"safety_max_consecutive_errors={value} 必须为正整数，"
            "fail-closed 回退为 1（连续 1 次异常即熔断）"
        )
        return 1
    return value


_cfg = env_config()
_MAX_ERRORS = _parse_max_errors(_cfg.get("safety_max_consecutive_errors", "3"))
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


class InterlockConfigError(RuntimeError):
    """互锁规则/写入地址映射配置未成功加载（fail-closed 状态）。"""


class WriteValidator:
    def __init__(self):
        self._lock = threading.RLock()
        self.consecutive_errors = 0
        self._rules: list[dict] = []
        self._rules_by_target: dict[str, list[dict]] = {}
        self._s7_write_addresses: dict[str, dict[str, str]] = {}
        self._last_write_time: dict[str, float] = {}
        self._bit_reader = None
        self._interlock_loaded = False
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
        """加载互锁规则文件；缺失或解析/校验异常时置 _interlock_loaded=False（fail-closed）"""
        self._interlock_loaded = False
        self._rules = []
        self._rules_by_target = {}
        self._s7_write_addresses = {}
        if not RULES_FILE.exists():
            _logger.error(f"互锁规则文件不存在（拒绝写入）: {RULES_FILE}")
            return
        try:
            data = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8")) or {}
            raw_rules = data.get("write_rules", [])
            if not isinstance(raw_rules, list) or not raw_rules:
                raise ValueError("write_rules 必须是非空列表")
            self._rules = raw_rules
            self._rules_by_target = {}
            for rule in self._rules:
                if not isinstance(rule, dict):
                    raise ValueError(f"互锁规则格式无效: {rule!r}")
                target = rule.get("target")
                if isinstance(target, str) and target:
                    self._rules_by_target.setdefault(target.upper(), []).append(rule)
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
            self._interlock_loaded = True
            _logger.info(f"已加载 {len(self._rules)} 条互锁规则")
        except Exception as e:
            self._rules = []
            self._rules_by_target = {}
            self._s7_write_addresses = {}
            self._interlock_loaded = False
            _logger.error(f"加载互锁规则失败（fail-closed，拒绝写入）: {e}")

    @staticmethod
    def _normalize_s7_address(address: str) -> str:
        if not isinstance(address, str):
            raise ValueError("S7 地址必须是字符串")
        normalized = "".join(address.upper().split())
        if not normalized:
            raise ValueError("S7 地址不能为空")
        return normalized

    def resolve_s7_write_address(self, address: str) -> dict[str, str] | None:
        """返回原始地址对应的安全语义；未显式配置时拒绝写入。

        Raises:
            InterlockConfigError: 互锁规则/地址映射未成功加载（与"正常未映射地址"
                可区分，便于调用方与审计记录配置加载失败）。
        """
        if not self._interlock_loaded:
            raise InterlockConfigError("互锁规则配置加载失败，无法解析写入地址")
        try:
            normalized = self._normalize_s7_address(address)
        except ValueError:
            return None
        mapping = self._s7_write_addresses.get(normalized)
        return dict(mapping) if mapping else None

    def _check_interlock_rules(
        self,
        tag_name: str,
        value: Any,
        numeric_value: float | None,
        prefetched_bits: dict[str, Any] | None = None,
    ) -> ValidationResult | None:
        """检查互锁规则（require_bits, max_value, min_value, cooldown）

        规则目标匹配大小写不敏感；同一 target 的全部规则都必须通过，
        任一规则拒绝即拒绝写入；命中数值约束规则的非数值写入 fail-closed。
        """
        tag_key = str(tag_name).upper()
        rules = self._rules_by_target.get(tag_key, ())
        for rule in rules:
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
                    try:
                        bit_val = prefetched_bits[bit_addr] if prefetched_bits else None
                    except (KeyError, TypeError):
                        bit_val = None
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

            # 数值范围检查（非数值写入对数值互锁规则 fail-closed）
            has_numeric_constraints = any(
                rule.get(k) is not None
                for k in ("max_value", "min_value", "cooldown_seconds")
            )
            if numeric_value is None:
                if has_numeric_constraints:
                    self.consecutive_errors += 1
                    return ValidationResult(False, f"互锁规则要求数值，收到非数值: {value!r}")
                continue
            if not math.isfinite(numeric_value):
                self.consecutive_errors += 1
                return ValidationResult(False, f"值必须是有限数值: {value}")

            max_val = rule.get("max_value")
            if max_val is not None and numeric_value > max_val:
                self.consecutive_errors += 1
                return ValidationResult(False, f"超出最大值限制: {numeric_value} > {max_val}")

            min_val = rule.get("min_value")
            if min_val is not None and numeric_value < min_val:
                self.consecutive_errors += 1
                return ValidationResult(False, f"低于最小值限制: {numeric_value} < {min_val}")

            # 冷却时间检查
            cooldown = rule.get("cooldown_seconds")
            if cooldown:
                last_time = self._last_write_time.get(tag_key, 0)
                elapsed = time.time() - last_time
                if elapsed < cooldown:
                    return ValidationResult(
                        False,
                        f"冷却时间未到: 还需等待 {cooldown - elapsed:.1f}s"
                    )

        # 全部规则通过后统一记录写入时间（同一 target 多规则共享时间基准）
        if rules:
            self._last_write_time[tag_key] = time.time()
        return None

    def _prefetch_required_bits(self, tag_name: str) -> dict[str, Any]:
        """在锁外读取互锁规则所需安全位状态（PLC 网络 I/O 不持锁）。

        位读取失败或回调异常一律记为 None，由锁内检查按 fail-closed 拒绝，
        原始异常只记录到日志，不向调用方泄漏。
        """
        if self._bit_reader is None:
            return {}
        tag_key = str(tag_name).upper()
        required: list[Any] = []
        for rule in self._rules_by_target.get(tag_key, ()):
            require_bits = rule.get("require_bits")
            if isinstance(require_bits, list):
                required.extend(require_bits)
        states: dict[str, Any] = {}
        for bit_addr in required:
            try:
                states[bit_addr] = self._bit_reader(bit_addr)
            except Exception as exc:
                _logger.error(f"安全位读取异常: {bit_addr!r}: {exc}")
                if isinstance(bit_addr, str):
                    states[bit_addr] = None
        return states

    def validate(self, tag_name: str, value, current_value=None) -> ValidationResult:
        # PLC 位读取（网络 I/O）在锁外执行，避免所有并发写校验被 PLC 往返延迟串行化
        prefetched_bits = self._prefetch_required_bits(tag_name)
        with self._lock:
            return self._validate_locked(tag_name, value, current_value, prefetched_bits)

    def _validate_locked(
        self,
        tag_name: str,
        value,
        current_value=None,
        prefetched_bits: dict[str, Any] | None = None,
    ) -> ValidationResult:
        # 0. 互锁规则未成功加载 → fail-closed 拒绝所有写入
        if not self._interlock_loaded:
            self.consecutive_errors += 1
            return ValidationResult(False, "互锁规则加载失败，拒绝写入")

        tag_upper = str(tag_name).upper()

        # 1. 检查禁止写入的安全标签
        for pat in FORBIDDEN_PATTERNS:
            if re.match(pat, tag_upper):
                self.consecutive_errors += 1
                return ValidationResult(False, f"禁止写入安全标签: {tag_name}")

        # 2. 检查熔断状态
        if self.consecutive_errors >= _MAX_ERRORS:
            return ValidationResult(False, f"熔断: 连续 {self.consecutive_errors} 次异常，请人工介入重置")

        # 数值转换只做一次（互锁范围/全局范围/跳变检测复用）
        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
            numeric_value = None

        # 3. 检查互锁规则（max/min/cooldown）
        rule_result = self._check_interlock_rules(
            tag_name, value, numeric_value, prefetched_bits
        )
        if rule_result is not None:
            return rule_result

        # 4. 全局合理范围检查（仅数值标量）
        is_numeric_scalar = isinstance(value, (int, float)) and not isinstance(value, bool)
        if is_numeric_scalar:
            if not math.isfinite(numeric_value):
                self.consecutive_errors += 1
                return ValidationResult(False, f"值必须是有限数值: {value}")
            if abs(numeric_value) > 1_000_000:
                self.consecutive_errors += 1
                return ValidationResult(False, f"值 {value} 超出合理范围")

        # 5. 值跳变检测
        if (current_value is not None
                and is_numeric_scalar
                and isinstance(current_value, (int, float))
                and not isinstance(current_value, bool)):
            current_numeric = float(current_value)
            if abs(current_numeric) > 0.001:
                if abs(numeric_value - current_numeric) > abs(current_numeric) * 10:
                    self.consecutive_errors += 1
                    return ValidationResult(False, f"值跳变过大: {current_value} -> {value}")

        # 通过所有检查，重置连续错误计数
        needs = _WRITE_CONFIRM and any(
            re.match(p, tag_upper) for p in CONFIRM_PATTERNS
        )
        self.consecutive_errors = 0
        return ValidationResult(True, "OK", needs_confirmation=needs)


validator = WriteValidator()
