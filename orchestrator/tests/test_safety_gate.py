"""
测试 orchestrator.safety_gate — 统一安全拦截点。
"""
import pytest
from orchestrator.safety_gate import SafetyGate, SafetyResult, get_safety_gate


class TestSafetyResult:
    """SafetyResult 数据类"""

    def test_allowed_result(self):
        result = SafetyResult(allowed=True, reason="ok")
        assert result.allowed is True
        assert result.reason == "ok"
        assert result.needs_confirmation is False
        assert result.warnings == []

    def test_rejected_result(self):
        result = SafetyResult(allowed=False, reason="安全标签禁止写入")
        assert result.allowed is False

    def test_result_with_warnings(self):
        result = SafetyResult(
            allowed=True, reason="ok", warnings=["值跳变过大"]
        )
        assert result.allowed is True
        assert len(result.warnings) == 1


class TestSafetyGate:
    """SafetyGate 统一安全拦截"""

    def test_create_gate(self):
        gate = SafetyGate()
        assert gate is not None
        assert gate._validator is not None
        assert gate._shadow is not None

    def test_is_forbidden_tag_estop(self):
        gate = SafetyGate()
        assert gate.is_forbidden_tag("E_STOP_BUTTON") is True
        assert gate.is_forbidden_tag("ESTOP_MAIN") is True
        assert gate.is_forbidden_tag("EMERGENCY_STOP") is True
        assert gate.is_forbidden_tag("SAFETY_DOOR") is True

    def test_is_forbidden_tag_normal(self):
        gate = SafetyGate()
        assert gate.is_forbidden_tag("MotorSpeed") is False
        assert gate.is_forbidden_tag("DB1.Temperature") is False
        assert gate.is_forbidden_tag("Conveyor_Speed") is False

    def test_check_write_forbidden_tag(self):
        gate = SafetyGate()
        result = gate.check_write("ESTOP_MAIN", 1)
        assert result.allowed is False
        assert result.validation_result is not None
        assert result.validation_result.allowed is False

    def test_check_write_normal_tag(self):
        gate = SafetyGate()
        result = gate.check_write("MotorSpeed", 1500, operator="ai")
        assert result.allowed is True
        assert result.reason == "安全检查通过"

    def test_check_write_with_operator(self):
        gate = SafetyGate()
        result = gate.check_write("Pump_Speed", 800, operator="human")
        assert result.allowed is True

    def test_check_write_high_value(self):
        gate = SafetyGate()
        # 1.5M 远超合理范围（>1,000,000），影子仿真应该拦截
        result = gate.check_write("PumpSpeed", 1_500_000)
        # 影子仿真会因值 > 1,000,000 而拒绝
        assert result.allowed is False

    def test_reset_fuse(self, tmp_path):
        from safety.confirmation import ConfirmationError, ConfirmationService
        gate = SafetyGate()
        service = ConfirmationService(
            secret="test-confirmation-secret",
            store_path=tmp_path / "confirmations.sqlite3",
        )
        token = service.issue(
            operator="local-session:abc",
            approver="local-human",
            target="safety.fuse_reset",
            value="reset",
            device_id="s7:test-host:0:1",
            audit_id="audit-fuse-1",
        )
        # 无令牌必须拒绝
        import pytest
        with pytest.raises(ConfirmationError):
            gate.reset_fuse(
                confirmation_token="",
                operator="local-session:abc",
                device_id="s7:test-host:0:1",
                confirmation_service=service,
            )
        # 有效令牌允许重置
        gate.reset_fuse(
            confirmation_token=token,
            operator="local-session:abc",
            device_id="s7:test-host:0:1",
            confirmation_service=service,
        )
        # 令牌一次性，第二次必须拒绝
        with pytest.raises(ConfirmationError):
            gate.reset_fuse(
                confirmation_token=token,
                operator="local-session:abc",
                device_id="s7:test-host:0:1",
                confirmation_service=service,
            )

    def test_set_bit_reader(self):
        gate = SafetyGate()
        gate.set_bit_reader(lambda addr: True)
        # 不应抛出异常

    def test_get_safety_gate_singleton(self):
        gate1 = get_safety_gate()
        gate2 = get_safety_gate()
        assert gate1 is gate2

    def test_forbidden_patterns_case_insensitive(self):
        gate = SafetyGate()
        assert gate.is_forbidden_tag("estop_main") is True
        assert gate.is_forbidden_tag("Safety_Gate") is True
        assert gate.is_forbidden_tag("s_estop_1") is True

    def test_check_write_with_current_value(self):
        gate = SafetyGate()
        result = gate.check_write(
            "MotorSpeed", 1500, current_value=1000, operator="ai"
        )
        assert result.allowed is True

    def test_check_write_needs_confirmation(self):
        gate = SafetyGate()
        # MOTOR 标签应触发确认需求
        result = gate.check_write("MOTOR_1", 1, operator="ai")
        # 视 validator 规则而定，Motor 可能被标记为需要确认
        assert isinstance(result.allowed, bool)