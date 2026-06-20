"""互锁规则加载与执行测试 — 验证 C2 修复"""
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "safety"))
sys.path.insert(0, str(PROJECT_ROOT / "mcp_common"))


class TestInterlockRulesLoading:
    """验证 validator 正确加载 interlock-rules.yml"""

    def test_rules_loaded(self):
        from safety.validator import WriteValidator
        v = WriteValidator()
        assert len(v._rules) > 0, "互锁规则未加载"

    def test_motor_speed_rule_exists(self):
        from safety.validator import WriteValidator
        v = WriteValidator()
        targets = [r["target"] for r in v._rules]
        assert "DB1.MotorSpeed" in targets

    def test_heater_power_rule_exists(self):
        from safety.validator import WriteValidator
        v = WriteValidator()
        targets = [r["target"] for r in v._rules]
        assert "DB1.HeaterPower" in targets


class TestInterlockMaxMin:
    """验证 max/min 值检查"""

    def _make_validator(self):
        from safety.validator import WriteValidator
        v = WriteValidator()
        v.set_bit_reader(lambda addr: True)  # mock: 所有安全位 OK
        return v

    def test_motor_speed_over_max_rejected(self):
        v = self._make_validator()
        result = v.validate("DB1.MotorSpeed", 3500)
        assert not result.allowed
        assert "最大值" in result.reason

    def test_motor_speed_below_min_rejected(self):
        v = self._make_validator()
        result = v.validate("DB1.MotorSpeed", -100)
        assert not result.allowed
        assert "最小值" in result.reason

    def test_motor_speed_within_range_allowed(self):
        v = self._make_validator()
        result = v.validate("DB1.MotorSpeed", 1500)
        assert result.allowed

    def test_heater_power_over_100_rejected(self):
        v = self._make_validator()
        result = v.validate("DB1.HeaterPower", 150)
        assert not result.allowed


class TestInterlockCooldown:
    """验证冷却时间检查"""

    def test_heater_cooldown_enforced(self):
        from safety.validator import WriteValidator
        v = WriteValidator()
        v.set_bit_reader(lambda addr: True)  # mock: 所有安全位 OK

        # 第一次写入应成功
        result1 = v.validate("DB1.HeaterPower", 50)
        assert result1.allowed

        # 立即第二次写入应被冷却时间拒绝
        result2 = v.validate("DB1.HeaterPower", 60)
        assert not result2.allowed
        assert "冷却时间" in result2.reason


class TestFuseTriggeredByOverrange:
    """验证超范围也触发熔断计数"""

    def test_overrange_increments_fuse(self):
        from safety.validator import WriteValidator
        v = WriteValidator()
        v.set_bit_reader(lambda addr: True)  # mock: 所有安全位 OK

        # 连续超范围写入
        v.validate("DB1.MotorSpeed", 5000)  # +1
        v.validate("DB1.MotorSpeed", 5000)  # +2
        v.validate("DB1.MotorSpeed", 5000)  # +3

        # 第 4 次即使正常值也应熔断
        result = v.validate("DB1.NormalTag", 50)
        assert not result.allowed
        assert "熔断" in result.reason
