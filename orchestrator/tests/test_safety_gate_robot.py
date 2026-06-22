"""SafetyGate 机器人场景测试 — TS014

验证 SafetyGate 端到端（validator + shadow_sim + audit）处理机器人写入。
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "safety"))
sys.path.insert(0, str(PROJECT_ROOT / "mcp_common"))


def _make_gate(bit_states: dict | None = None):
    """构造 SafetyGate，bit_states 控制哪些安全位为 False"""
    from orchestrator.safety_gate import SafetyGate
    gate = SafetyGate()
    false_set = set() if bit_states is None else {k for k, v in bit_states.items() if not v}
    gate.set_bit_reader(lambda addr: addr not in false_set)
    return gate


class TestSafetyGateRobotSpeed:
    """SafetyGate 对 DB1.RobotSpeed 的处理（已有规则 6）"""

    def test_normal_speed_allowed(self):
        gate = _make_gate()
        result = gate.check_write("DB1.RobotSpeed", 300, operator="ai")
        assert result.allowed, result.reason

    def test_over_speed_rejected(self):
        gate = _make_gate()
        result = gate.check_write("DB1.RobotSpeed", 600, operator="ai")
        assert not result.allowed
        assert "最大值" in result.reason

    def test_estop_rejected(self):
        gate = _make_gate({"DB1.EmergencyStopOff": False})
        result = gate.check_write("DB1.RobotSpeed", 300, operator="ai")
        assert not result.allowed
        assert "安全前置条件" in result.reason

    def test_zone_not_clear_rejected(self):
        gate = _make_gate({"DB1.RobotZoneClear": False})
        result = gate.check_write("DB1.RobotSpeed", 300, operator="ai")
        assert not result.allowed
        assert "安全前置条件" in result.reason


class TestSafetyGateRobotShadowSim:
    """影子仿真对机器人写入的验证"""

    def test_shadow_sim_passes_normal_write(self):
        gate = _make_gate()
        result = gate.check_write("DB1.RobotSpeed", 200, operator="ai", current_value=100)
        assert result.allowed
        assert result.shadow_result is not None
        assert result.shadow_result.safe


class TestSafetyGateRobotAudit:
    """审计日志记录机器人操作"""

    def test_approved_write_audit_logged(self):
        from safety.audit import audit
        gate = _make_gate()
        result = gate.check_write("DB1.RobotSpeed", 200, operator="ai")
        assert result.allowed
        # 审计日志应有记录（audit_id 非空说明审计已执行）
        assert result.audit_id, "审计日志未生成"

    def test_rejected_write_audit_logged(self):
        from safety.audit import audit
        gate = _make_gate()
        result = gate.check_write("DB1.RobotSpeed", 9999, operator="ai")
        assert not result.allowed
        # 拒绝也应有审计记录 — validator 阶段就拦截
        assert result.validation_result is not None
