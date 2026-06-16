"""影子仿真验证器测试 — 覆盖核心安全逻辑"""
import pytest
import asyncio
from safety.shadow_simulator import ShadowSimulator, ShadowResult


@pytest.fixture
def sim():
    """每个测试用一个全新的 ShadowSimulator 实例"""
    return ShadowSimulator()


class TestForbiddenTags:
    """禁止写入的安全标签检测"""

    @pytest.mark.parametrize("tag", [
        "DB1.ESTOP_Signal",
        "EMERGENCY_STOP",
        "E_STOP_Relay",
        "SAFETY_Gate",
        "SAFE_Torque_Off",
        "S_ESTOP_Feedback",
    ])
    def test_forbidden_tag_rejected(self, sim, tag):
        result = asyncio.run(sim.simulate_write(tag, 1))
        assert not result.safe
        assert "禁止写入安全标签" in result.reason

    @pytest.mark.parametrize("tag", [
        "DB1.MotorSpeed",
        "DB1.ConveyorSpeed",
        "DB1.HeaterPower",
        "MW10",
    ])
    def test_normal_tag_allowed(self, sim, tag):
        result = asyncio.run(sim.simulate_write(tag, 100))
        assert result.safe


class TestValueBounds:
    """值范围检查"""

    def test_value_exceeds_max(self, sim):
        result = asyncio.run(sim.simulate_write("DB1.Motor", 2_000_000))
        assert not result.safe
        assert "超出合理范围" in result.reason

    def test_value_within_range(self, sim):
        result = asyncio.run(sim.simulate_write("DB1.Motor", 999_999))
        assert result.safe

    def test_negative_extreme(self, sim):
        result = asyncio.run(sim.simulate_write("DB1.Motor", -2_000_000))
        assert not result.safe


class TestChangeRate:
    """值跳变检测"""

    def test_large_jump_rejected(self, sim):
        # 先写入一个基准值
        asyncio.run(sim.simulate_write("DB1.Speed", 100))
        # 然后跳变 > 10x
        result = asyncio.run(sim.simulate_write("DB1.Speed", 5000))
        assert not result.safe
        assert "跳变过大" in result.reason

    def test_gradual_change_allowed(self, sim):
        asyncio.run(sim.simulate_write("DB1.Speed", 100))
        result = asyncio.run(sim.simulate_write("DB1.Speed", 150))
        assert result.safe

    def test_first_write_no_history(self, sim):
        result = asyncio.run(sim.simulate_write("DB1.NewTag", 5000))
        assert result.safe  # 无历史，不检查跳变


class TestShadowResult:
    """ShadowResult 数据结构"""

    def test_safe_result(self, sim):
        result = asyncio.run(sim.simulate_write("DB1.OK", 50))
        assert result.safe
        assert result.reason == "仿真通过"
        assert result.predicted_value == 50

    def test_unsafe_result_has_warnings(self, sim):
        result = asyncio.run(sim.simulate_write("DB1.ESTOP", 1))
        assert not result.safe
        assert result.reason != ""
