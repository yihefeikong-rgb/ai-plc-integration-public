"""机器人安全互锁规则测试 — TS014

验证新增的 3 条机器人规则（GripperPressure / JointAngle / RobotConveyorSpeed）
经 WriteValidator 正确拦截。
"""
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "safety"))
sys.path.insert(0, str(PROJECT_ROOT / "mcp_common"))


def _make_validator(bit_states: dict | None = None):
    """构造 WriteValidator，bit_states 控制哪些安全位为 False"""
    from safety.validator import WriteValidator
    v = WriteValidator()
    default_true = {"DB1.SafetyOK", "DB1.EmergencyStopOff", "DB1.RobotZoneClear"}
    false_set = set() if bit_states is None else {k for k, v2 in bit_states.items() if not v2}
    v.set_bit_reader(lambda addr: addr not in false_set)
    return v


class _FakeClock:
    """固定不走的假时钟：仅替换 validator 模块内的 time 引用。

    用于把冷却互锁测试与墙钟解耦：两次 validate() 之间的 elapsed 恒为 0，
    慢 CI/GC/调试下不会因 elapsed>=cooldown 产生假失败；也不像全局
    time.time monkeypatch 那样污染同进程其他测试。
    """

    def time(self):
        return 1000.0


# ── DB1.GripperPressure（0-100, SafetyOK+EmergencyStopOff, cooldown=1s） ─────


class TestGripperPressure:
    TAG = "DB1.GripperPressure"

    def test_within_range_allowed(self):
        v = _make_validator()
        result = v.validate(self.TAG, 50)
        assert result.allowed, result.reason

    def test_over_max_rejected(self):
        v = _make_validator()
        result = v.validate(self.TAG, 150)
        assert not result.allowed
        assert "最大值" in result.reason

    def test_below_min_rejected(self):
        v = _make_validator()
        result = v.validate(self.TAG, -10)
        assert not result.allowed
        assert "最小值" in result.reason

    def test_safety_ok_false_rejected(self):
        v = _make_validator({"DB1.SafetyOK": False})
        result = v.validate(self.TAG, 50)
        assert not result.allowed
        assert "安全前置条件" in result.reason

    def test_emergency_stop_off_false_rejected(self):
        v = _make_validator({"DB1.EmergencyStopOff": False})
        result = v.validate(self.TAG, 50)
        assert not result.allowed
        assert "安全前置条件" in result.reason

    def test_cooldown_enforced(self, monkeypatch):
        v = _make_validator()
        # cooldown=1s：两次 validate 必须落在冷却窗口内。用假时钟替换
        # validator 模块内的 time 引用（不触碰进程级 time.time），
        # 消除慢 CI/GC/调试下 elapsed>=cooldown 导致的墙钟竞态。
        import safety.validator as validator_mod
        monkeypatch.setattr(validator_mod, "time", _FakeClock())
        r1 = v.validate(self.TAG, 50)
        assert r1.allowed, r1.reason
        r2 = v.validate(self.TAG, 60)
        assert not r2.allowed
        assert "冷却时间" in r2.reason


# ── DB1.JointAngle（±180, SafetyOK+RobotZoneClear, cooldown=3s） ─────────────


class TestJointAngle:
    TAG = "DB1.JointAngle"

    def test_positive_within_range(self):
        v = _make_validator()
        result = v.validate(self.TAG, 90)
        assert result.allowed, result.reason

    def test_over_max_rejected(self):
        v = _make_validator()
        result = v.validate(self.TAG, 200)
        assert not result.allowed
        assert "最大值" in result.reason

    def test_negative_within_range(self):
        v = _make_validator()
        result = v.validate(self.TAG, -45)
        assert result.allowed, result.reason

    def test_robot_zone_clear_false_rejected(self):
        v = _make_validator({"DB1.RobotZoneClear": False})
        result = v.validate(self.TAG, 90)
        assert not result.allowed
        assert "安全前置条件" in result.reason


# ── DB1.RobotConveyorSpeed（0-2000, SafetyOK+EmergencyStopOff, cooldown=2s） ─


class TestRobotConveyorSpeed:
    TAG = "DB1.RobotConveyorSpeed"

    def test_within_range_allowed(self):
        v = _make_validator()
        result = v.validate(self.TAG, 1000)
        assert result.allowed, result.reason

    def test_over_max_rejected(self):
        v = _make_validator()
        result = v.validate(self.TAG, 2500)
        assert not result.allowed
        assert "最大值" in result.reason

    def test_emergency_stop_off_false_rejected(self):
        v = _make_validator({"DB1.EmergencyStopOff": False})
        result = v.validate(self.TAG, 1000)
        assert not result.allowed
        assert "安全前置条件" in result.reason
