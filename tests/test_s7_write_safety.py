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

# 认证门禁要求显式传入与 conftest 一致的服务端令牌（修复：不再回退到服务器自身令牌）
_AUTH_TOKEN = "pytest-mcp-auth-token"


class TestS7WriteSafetyGuard:
    """测试安全模块不可用时的行为"""

    def test_write_rejected_when_safety_unavailable(self):
        """安全模块缺失时，写入必须被拒绝"""
        import tools_s7
        original = tools_s7.SAFETY_AVAILABLE

        tools_s7.SAFETY_AVAILABLE = False
        try:
            result = asyncio.run(tools_s7.s7_write("MW10", "100", auth_token=_AUTH_TOKEN))
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

        result = asyncio.run(tools_s7.s7_write("M0.1", "true", auth_token=_AUTH_TOKEN))

        assert "需要人工确认" in result
        mock_adapter.write_address.assert_not_called()

    @patch("tools_s7.adapter")
    def test_forbidden_tag_rejected(self, mock_adapter, monkeypatch):
        """安全标签（ESTOP 等）写入必须被拒绝"""
        import tools_s7
        from safety.validator import validator

        # 共享单例（熔断计数 / SAFETY_AVAILABLE）用 monkeypatch 管理，
        # 测试结束自动恢复，不向后续测试泄漏状态（与执行顺序解耦）。
        monkeypatch.setattr(validator, "consecutive_errors", 0)
        monkeypatch.setattr(tools_s7, "SAFETY_AVAILABLE", True)

        # 现有映射没有指向禁止标签的地址；注入一个映射到 ESTOP 语义的地址，
        # 让真实校验器走到 FORBIDDEN_PATTERNS 检查（而非在“未映射”守卫处被拒）。
        monkeypatch.setattr(
            tools_s7.safety_val,
            "resolve_s7_write_address",
            lambda addr: {"target": "DB1.ESTOP_Signal", "type": "bool"},
        )
        mock_adapter.parse_write_value.return_value = True

        result = asyncio.run(tools_s7.s7_write("M0.1", "1", auth_token=_AUTH_TOKEN))
        assert "禁止写入安全标签" in result
        mock_adapter.write_address.assert_not_called()

    @patch("tools_s7.adapter")
    def test_value_exceeds_interlock_max(self, mock_adapter, monkeypatch):
        """超出互锁规则 max_value 时被拒绝"""
        import tools_s7
        from safety.validator import validator

        # 进入时熔断计数必须为 0：否则会先命中熔断分支而非互锁 max_value，
        # 结果与执行顺序强耦合；monkeypatch 保证自动恢复（顺序无关）。
        monkeypatch.setattr(validator, "consecutive_errors", 0)
        monkeypatch.setattr(tools_s7, "SAFETY_AVAILABLE", True)

        # 让真实校验器拿到数值 5000：裸 MagicMock 的 float()==1.0 会绕过 max_value，
        # 使拒绝实际来自 needs_confirmation 路径而非互锁。
        mock_adapter.parse_write_value.return_value = 5000

        # MW14 映射到 DB1.MotorSpeed，后者 max_value=3000
        result = asyncio.run(tools_s7.s7_write("MW14", "5000", auth_token=_AUTH_TOKEN))
        assert "超出最大值限制" in result
        mock_adapter.write_address.assert_not_called()

    @patch("tools_s7.adapter")
    def test_unmapped_address_is_rejected(self, mock_adapter, monkeypatch):
        """未映射的原始地址不得因数值正常而写入。"""
        import tools_s7
        monkeypatch.setattr(tools_s7, "SAFETY_AVAILABLE", True)
        mock_adapter.write_address.return_value = "✅ 写入成功"

        result = asyncio.run(tools_s7.s7_write("MW10", "100", auth_token=_AUTH_TOKEN))
        assert "未映射" in result
        mock_adapter.write_address.assert_not_called()


class TestS7WriteFuse:
    """测试熔断机制"""

    @patch("tools_s7.adapter")
    def test_fuse_after_consecutive_errors(self, mock_adapter, monkeypatch):
        """连续异常后触发熔断"""
        import tools_s7
        import safety.validator as validator_module
        from safety.validator import validator

        # 熔断计数与 SAFETY_AVAILABLE 用 monkeypatch 管理：即使断言失败，
        # 测试结束也会自动恢复共享单例，不向后续测试泄漏熔断状态（顺序无关）。
        monkeypatch.setattr(validator, "consecutive_errors", 0)
        monkeypatch.setattr(tools_s7, "SAFETY_AVAILABLE", True)

        # 原始地址在映射前就会拒绝；直接触发安全标签校验以建立熔断状态。
        # 阈值取校验器自身配置，不依赖环境变量 safety_max_consecutive_errors 恰为 3。
        for _ in range(validator_module._MAX_ERRORS):
            validator.validate("SAFETY_TAG_1", 1)

        # 原始地址映射先于联锁；将熔断状态置入校验器后，映射地址也必须被阻断。
        result = asyncio.run(tools_s7.s7_write("MW14", "100", auth_token=_AUTH_TOKEN))
        assert "熔断" in result


class TestS7WriteAudit:
    """测试审计日志记录"""

    @patch("tools_s7._audit")
    @patch("tools_s7.adapter")
    @patch("tools_s7.shadow_sim")
    def test_successful_write_logged(self, mock_sim, mock_adapter, mock_audit, monkeypatch):
        """成功写入应记录审计日志"""
        import tools_s7
        monkeypatch.setattr(tools_s7, "SAFETY_AVAILABLE", True)

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

        asyncio.run(tools_s7.s7_write("MW14", "50", auth_token=_AUTH_TOKEN))
        mock_audit.begin_control_operation.assert_called_once()
        call_kwargs = mock_audit.log.call_args
        assert call_kwargs.args[0] == "write"
        assert call_kwargs.args[1] == "MW14"
        # 修复后审计归属真实认证身份（MCP_AUTH_TOKEN 派生 s7:<hash>），不再是空主体
        assert call_kwargs.kwargs.get("operator", "").startswith("s7:")
        assert call_kwargs.kwargs.get("success") is True
        assert call_kwargs.kwargs.get("detail") == "semantic_target=DB1.MotorSpeed"

    @patch("tools_s7._audit")
    @patch("tools_s7.adapter")
    def test_rejected_write_logged(self, mock_adapter, mock_audit, monkeypatch):
        """被拒绝的写入应记录审计日志"""
        import tools_s7
        monkeypatch.setattr(tools_s7, "SAFETY_AVAILABLE", True)

        asyncio.run(tools_s7.s7_write("EMERGENCY_STOP", "1", auth_token=_AUTH_TOKEN))
        mock_audit.log.assert_called()
        call_args = mock_audit.log.call_args
        assert call_args[1].get("success") is False or call_args[0][0] == "write_rejected"
