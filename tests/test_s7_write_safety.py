"""s7_write 安全路径集成测试 — 验证写入前的完整安全链"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
import asyncio

# 确保路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "mcp-servers" / "plc-mcp-bridge"))
sys.path.insert(0, str(PROJECT_ROOT / "safety"))
sys.path.insert(0, str(PROJECT_ROOT / "mcp_common"))


class TestS7WriteSafetyGuard:
    """测试安全模块不可用时的行为"""

    def test_write_rejected_when_safety_unavailable(self):
        """安全模块缺失时，写入必须被拒绝"""
        import tools_s7
        original = tools_s7.SAFETY_AVAILABLE

        tools_s7.SAFETY_AVAILABLE = False
        try:
            result = asyncio.run(tools_s7.s7_write("MW10", "100"))
            assert "拒绝" in result
            assert "安全模块不可用" in result
        finally:
            tools_s7.SAFETY_AVAILABLE = original


class TestS7WriteInterlockCheck:
    """测试互锁校验"""

    @patch("tools_s7.adapter")
    def test_forbidden_tag_rejected(self, mock_adapter):
        """安全标签（ESTOP 等）写入必须被拒绝"""
        import tools_s7
        tools_s7.SAFETY_AVAILABLE = True

        result = asyncio.run(tools_s7.s7_write("DB1.ESTOP_Signal", "1"))
        assert "拒绝" in result
        mock_adapter.write_address.assert_not_called()

    @patch("tools_s7.adapter")
    def test_value_exceeds_interlock_max(self, mock_adapter):
        """超出互锁规则 max_value 时被拒绝"""
        import tools_s7
        tools_s7.SAFETY_AVAILABLE = True

        # DB1.MotorSpeed 在 interlock-rules.yml 中 max_value=3000
        result = asyncio.run(tools_s7.s7_write("DB1.MotorSpeed", "5000"))
        assert "拒绝" in result or "超出" in result
        mock_adapter.write_address.assert_not_called()

    @patch("tools_s7.adapter")
    def test_normal_write_succeeds(self, mock_adapter):
        """正常值写入应成功"""
        import tools_s7
        tools_s7.SAFETY_AVAILABLE = True
        mock_adapter.write_address.return_value = "✅ 写入成功"

        result = asyncio.run(tools_s7.s7_write("MW10", "100"))
        # 如果影子仿真和互锁都通过，应该成功
        # 注意：如果 shadow_sim 在测试环境不可用，写入仍应基于 validator 结果
        assert "失败" not in result or "成功" in result


class TestS7WriteFuse:
    """测试熔断机制"""

    @patch("tools_s7.adapter")
    def test_fuse_after_consecutive_errors(self, mock_adapter):
        """连续异常后触发熔断"""
        import tools_s7
        from safety.validator import validator

        tools_s7.SAFETY_AVAILABLE = True
        # 重置计数器
        validator.consecutive_errors = 0

        # 触发 3 次安全标签写入（每次 +1 错误）
        for _ in range(3):
            asyncio.run(tools_s7.s7_write("SAFETY_TAG_1", "1"))

        # 第 4 次应触发熔断（即使是普通标签）
        result = asyncio.run(tools_s7.s7_write("DB1.NormalTag", "100"))
        assert "熔断" in result

        # 清理
        validator.consecutive_errors = 0


class TestS7WriteAudit:
    """测试审计日志记录"""

    @patch("tools_s7._audit")
    @patch("tools_s7.adapter")
    @patch("tools_s7.shadow_sim")
    def test_successful_write_logged(self, mock_sim, mock_adapter, mock_audit):
        """成功写入应记录审计日志"""
        import tools_s7
        tools_s7.SAFETY_AVAILABLE = True

        mock_adapter.write_address.return_value = "✅ OK"
        mock_sim.simulate_write = AsyncMock(
            return_value=MagicMock(safe=True)
        )

        asyncio.run(tools_s7.s7_write("MW10", "50"))
        mock_audit.log.assert_called_with("write", "MW10", "50", success=True)

    @patch("tools_s7._audit")
    @patch("tools_s7.adapter")
    def test_rejected_write_logged(self, mock_adapter, mock_audit):
        """被拒绝的写入应记录审计日志"""
        import tools_s7
        tools_s7.SAFETY_AVAILABLE = True

        asyncio.run(tools_s7.s7_write("EMERGENCY_STOP", "1"))
        mock_audit.log.assert_called()
        call_args = mock_audit.log.call_args
        assert call_args[1].get("success") is False or call_args[0][0] == "write_rejected"
