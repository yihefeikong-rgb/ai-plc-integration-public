"""s7_write 安全路径集成测试 — 验证写入前的完整安全链"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
import asyncio

# 确保路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT / "mcp-servers" / "plc-mcp-bridge"))
sys.path.append(str(PROJECT_ROOT / "safety"))
sys.path.append(str(PROJECT_ROOT / "mcp_common"))


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

    def test_confirmation_required_rejects_before_adapter_write(self, monkeypatch):
        """需要人工确认的写入不得到达 S7 适配器。"""
        import tools_s7

        mock_adapter = MagicMock()
        mock_adapter.parse_write_value.return_value = True
        mock_adapter.write_address.return_value = "不应写入"
        mock_validator = MagicMock()
        mock_validator.resolve_s7_write_address.return_value = {
            "target": "DB1.MOTOR_RUN",
            "type": "bool",
        }
        mock_validator.validate.return_value = MagicMock(
            allowed=True,
            needs_confirmation=True,
            reason="需要人工确认",
        )

        monkeypatch.setattr(tools_s7, "SAFETY_AVAILABLE", True)
        monkeypatch.setattr(tools_s7, "adapter", mock_adapter)
        monkeypatch.setattr(tools_s7, "safety_val", mock_validator)
        monkeypatch.setattr(
            tools_s7,
            "shadow_sim",
            MagicMock(simulate_write=AsyncMock(return_value=MagicMock(safe=True))),
        )
        monkeypatch.setattr(tools_s7, "_audit", MagicMock())

        result = asyncio.run(tools_s7.s7_write("M0.1", "true"))

        assert "需要人工确认" in result
        mock_adapter.write_address.assert_not_called()

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

        # MW14 映射到 DB1.MotorSpeed，后者 max_value=3000
        result = asyncio.run(tools_s7.s7_write("MW14", "5000"))
        assert "拒绝" in result or "超出" in result
        mock_adapter.write_address.assert_not_called()

    @patch("tools_s7.adapter")
    def test_unmapped_address_is_rejected(self, mock_adapter):
        """未映射的原始地址不得因数值正常而写入。"""
        import tools_s7
        tools_s7.SAFETY_AVAILABLE = True
        mock_adapter.write_address.return_value = "✅ 写入成功"

        result = asyncio.run(tools_s7.s7_write("MW10", "100"))
        assert "未映射" in result
        mock_adapter.write_address.assert_not_called()


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

        # 原始地址在映射前就会拒绝；直接触发三次安全标签校验以建立熔断状态。
        for _ in range(3):
            validator.validate("SAFETY_TAG_1", 1)

        # 原始地址映射先于联锁；将熔断状态置入校验器后，映射地址也必须被阻断。
        result = asyncio.run(tools_s7.s7_write("MW14", "100"))
        assert "熔断" in result

        # 清理
        validator.consecutive_errors = 0


class TestS7WriteAudit:
    """测试审计日志记录"""

    @patch("tools_s7._audit")
    @patch("tools_s7.adapter")
    @patch("tools_s7.shadow_sim")
    def test_successful_write_logged(self, mock_sim, mock_adapter, mock_audit, monkeypatch):
        """成功写入应记录审计日志"""
        import tools_s7
        tools_s7.SAFETY_AVAILABLE = True

        mock_adapter.write_address.return_value = "✅ OK"
        mock_adapter.parse_write_value.return_value = 50
        mock_sim.simulate_write = AsyncMock(
            return_value=MagicMock(safe=True)
        )
        mock_validator = MagicMock()
        mock_validator.resolve_s7_write_address.return_value = {
            "target": "DB1.MotorSpeed",
            "type": "int16",
        }
        mock_validator.validate.return_value = MagicMock(
            allowed=True,
            needs_confirmation=False,
            reason="OK",
        )
        monkeypatch.setattr(tools_s7, "safety_val", mock_validator)

        asyncio.run(tools_s7.s7_write("MW14", "50"))
        mock_audit.begin_control_operation.assert_called_once()
        mock_audit.log.assert_called_with(
            "write", "MW14", "50", operator="", success=True,
            detail="semantic_target=DB1.MotorSpeed",
        )

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
