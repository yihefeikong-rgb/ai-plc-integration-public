import pytest

from safety.validator import WriteValidator, ValidationResult


@pytest.fixture
def v():
    """每次测试使用全新的 validator 实例，避免 consecutive_errors 状态污染"""
    inst = WriteValidator()
    inst.set_bit_reader(lambda addr: True)  # mock: 所有安全位 OK
    return inst


def test_blocks_estop_write(v):
    r = v.validate("DB1.ESTOP", True)
    assert not r.allowed
    assert "禁止写入安全标签" in r.reason


def test_blocks_emergency_write(v):
    r = v.validate("EMERGENCY_STOP_BUTTON", True)
    assert not r.allowed


def test_blocks_safety_prefix(v):
    r = v.validate("SAFETY_RELAY_OK", False)
    assert not r.allowed


def test_allows_normal_tag(v):
    r = v.validate("DB1.MotorSpeed", 1500)
    assert r.allowed


def test_blocks_out_of_range_value(v):
    r = v.validate("DB1.MotorSpeed", 9_999_999)
    assert not r.allowed


def test_blocks_value_jump(v):
    r = v.validate("DB1.MotorSpeed", 2000, current_value=100)
    assert not r.allowed


def test_allows_small_increment(v):
    r = v.validate("DB1.MotorSpeed", 150, current_value=100)
    assert r.allowed


def test_validator_returns_dataclass(v):
    r = v.validate("DB1.NormalTag", 42)
    assert isinstance(r, ValidationResult)
    assert isinstance(r.allowed, bool)
    assert isinstance(r.reason, str)


def test_normal_write_resets_errors(v):
    v.validate("DB1.ESTOP", True)
    assert v.consecutive_errors == 1
    r = v.validate("DB1.MotorSpeed", 1500)
    assert r.allowed
    assert v.consecutive_errors == 0


def test_consecutive_errors_counter(v):
    assert v.consecutive_errors == 0
    v.validate("DB1.ESTOP", True)
    assert v.consecutive_errors == 1
    v.validate("EMERGENCY", True)
    assert v.consecutive_errors == 2


def test_fuse_trips_on_max_errors(v):
    v.consecutive_errors = 3
    r = v.validate("DB1.NormalMotor", 1000)
    assert not r.allowed
    assert "熔断" in r.reason


def test_needs_confirmation_for_motor(v):
    r = v.validate("DB1.MOTOR_RUN", True)
    assert r.needs_confirmation


def test_needs_confirmation_for_robot(v):
    r = v.validate("ROBOT_GRIPPER_CLOSE", True)
    assert r.needs_confirmation


def test_no_confirmation_for_sensor(v):
    r = v.validate("DB1.SENSOR_TEMP", 25.0)
    assert not r.needs_confirmation
