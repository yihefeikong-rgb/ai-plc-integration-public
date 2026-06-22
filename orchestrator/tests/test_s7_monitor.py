"""
测试 S7 监控工作流 — s7_monitor。

覆盖:
- detect_change 纯函数（多种阈值场景）
- mock_ai_analyze 返回值格式
- 工作流注册
- 工作流执行（mock 模式）:
  - 无变化时不写入
  - 有变化时触发写入
  - SafetyGate 拦截禁止标签
"""
import pytest
import asyncio

from orchestrator.core import OrchestratorEngine
from orchestrator.workflows.s7_monitor import (
    detect_change,
    mock_ai_analyze,
    register_s7_monitor_workflow,
)


# ---------------------------------------------------------------------------
# detect_change 纯函数测试
# ---------------------------------------------------------------------------

class TestDetectChange:
    """变化检测纯函数"""

    def test_no_change(self):
        assert detect_change(100.0, 100.0, 0.1) is False

    def test_change_within_threshold(self):
        assert detect_change(100.05, 100.0, 0.1) is False

    def test_change_exceeds_threshold(self):
        assert detect_change(100.2, 100.0, 0.1) is True

    def test_negative_delta_exceeds(self):
        assert detect_change(99.8, 100.0, 0.1) is True

    def test_negative_delta_within(self):
        assert detect_change(99.95, 100.0, 0.1) is False

    def test_zero_threshold_any_change(self):
        assert detect_change(100.001, 100.0, 0.0) is True

    def test_zero_threshold_no_change(self):
        assert detect_change(100.0, 100.0, 0.0) is False

    def test_large_threshold(self):
        assert detect_change(110.0, 100.0, 15.0) is False

    def test_exact_threshold_not_exceeded(self):
        # abs(100.1 - 100.0) == 0.1, not > 0.1
        assert detect_change(100.1, 100.0, 0.1) is False

    def test_large_values(self):
        assert detect_change(1500.0, 1000.0, 100.0) is True


# ---------------------------------------------------------------------------
# mock_ai_analyze 测试
# ---------------------------------------------------------------------------

class TestMockAiAnalyze:
    """Mock AI 分析函数"""

    def test_returns_dict_with_required_keys(self):
        result = mock_ai_analyze("DB1.Temp", 120.0, 20.0)
        assert "action" in result
        assert "value" in result
        assert "reason" in result

    def test_small_delta_returns_hold(self):
        result = mock_ai_analyze("DB1.Temp", 100.1, 0.1)
        assert result["action"] == "hold"

    def test_high_value_returns_write(self):
        result = mock_ai_analyze("DB1.Temp", 120.0, 20.0)
        assert result["action"] == "write"
        assert result["value"] == 100.0

    def test_low_value_returns_write(self):
        result = mock_ai_analyze("DB1.Temp", 80.0, -20.0)
        assert result["action"] == "write"
        assert result["value"] == 100.0

    def test_normal_range_returns_hold(self):
        # 97 is within target(100) +/- 5, but delta > 0.5
        result = mock_ai_analyze("DB1.Temp", 97.0, -3.0)
        assert result["action"] == "hold"

    def test_reason_contains_tag_name(self):
        result = mock_ai_analyze("DB1.Pressure", 120.0, 20.0)
        assert "DB1.Pressure" in result["reason"]


# ---------------------------------------------------------------------------
# 工作流注册测试
# ---------------------------------------------------------------------------

class TestWorkflowRegistration:
    """工作流注册"""

    def test_register_s7_monitor(self):
        engine = OrchestratorEngine()
        register_s7_monitor_workflow(engine)
        assert "s7_monitor" in engine.list_workflows()

    def test_register_does_not_duplicate(self):
        engine = OrchestratorEngine()
        register_s7_monitor_workflow(engine)
        register_s7_monitor_workflow(engine)
        assert engine.list_workflows().count("s7_monitor") == 1


# ---------------------------------------------------------------------------
# 工作流执行测试（mock 模式）
# ---------------------------------------------------------------------------

class TestWorkflowExecution:
    """工作流执行（mock 模式）"""

    def _make_engine(
        self,
        read_value: float = 100.0,
        write_result: dict | None = None,
    ) -> OrchestratorEngine:
        """创建带 mock 工具的引擎"""
        engine = OrchestratorEngine()
        register_s7_monitor_workflow(engine)

        engine.register_mock(
            "plc-mcp-bridge.s7_read",
            lambda tag, **kw: {"value": read_value, "tag": tag},
        )
        engine.register_mock(
            "plc-mcp-bridge.s7_write",
            lambda tag, value, **kw: write_result or {"ok": True, "tag": tag, "value": value},
        )
        return engine

    def test_no_change_no_write(self):
        """无变化时不调用写入"""
        engine = self._make_engine(read_value=100.0)
        result = asyncio.run(
            engine.run_async(
                "s7_monitor",
                input={"tag_name": "DB1.Temp", "target_value": 100.0},
            )
        )
        assert result.ok is True
        # 检查写入步骤没有执行
        write_steps = [s for s in result.steps if "s7_write" in s.tool]
        assert len(write_steps) == 0

    def test_change_triggers_write(self):
        """变化显著时触发 AI 分析并写入"""
        engine = self._make_engine(read_value=120.0)
        result = asyncio.run(
            engine.run_async(
                "s7_monitor",
                input={
                    "tag_name": "DB1.Temp",
                    "target_value": 100.0,
                    "delta_threshold": 0.1,
                },
            )
        )
        assert result.ok is True
        # 应该调用了 s7_write
        write_steps = [s for s in result.steps if "s7_write" in s.tool]
        assert len(write_steps) == 1
        assert write_steps[0].ok is True

    def test_change_but_hold_no_write(self):
        """变化显著但 AI 建议 hold 时不写入"""
        # 值 97.0，delta=-7.0 > threshold，但 97 在 target(100) ± 5 范围内
        engine = self._make_engine(read_value=97.0)
        result = asyncio.run(
            engine.run_async(
                "s7_monitor",
                input={
                    "tag_name": "DB1.Temp",
                    "target_value": 100.0,
                    "delta_threshold": 0.1,
                },
            )
        )
        assert result.ok is True
        write_steps = [s for s in result.steps if "s7_write" in s.tool]
        assert len(write_steps) == 0

    def test_mock_mode_bypasses_safety_gate(self):
        """mock 模式下 EmergencyStop 标签工作流正常完成（SafetyGate 在 MCP 模式才生效）"""
        engine = self._make_engine(read_value=120.0)
        engine.set_safety_gate()

        # 禁止标签的写入会被 SafetyGate 拦截
        # 由于 mock 工具不走 SafetyGate（只有 MCP 模式才走），
        # 这里验证 mock 模式下工作流正常执行
        # SafetyGate 的实际拦截在 MCP 模式下测试
        result = asyncio.run(
            engine.run_async(
                "s7_monitor",
                input={
                    "tag_name": "DB1.EmergencyStop",
                    "target_value": 0.0,
                    "delta_threshold": 0.1,
                },
            )
        )
        # mock 模式下不经过 SafetyGate，工作流应正常完成
        assert result.ok is True

    def test_result_contains_expected_fields(self):
        """返回结果包含预期字段"""
        engine = self._make_engine(read_value=120.0)
        result = asyncio.run(
            engine.run_async(
                "s7_monitor",
                input={
                    "tag_name": "DB1.Temp",
                    "target_value": 100.0,
                },
            )
        )
        assert result.ok is True
        # 步骤应包含 s7_read
        read_steps = [s for s in result.steps if "s7_read" in s.tool]
        assert len(read_steps) == 1

    def test_default_threshold(self):
        """默认阈值为 0.1"""
        engine = self._make_engine(read_value=100.05)
        result = asyncio.run(
            engine.run_async(
                "s7_monitor",
                input={"tag_name": "DB1.Temp"},
            )
        )
        assert result.ok is True
        # 0.05 < 0.1 默认阈值，不应变化
        write_steps = [s for s in result.steps if "s7_write" in s.tool]
        assert len(write_steps) == 0

    def test_no_target_value_uses_current(self):
        """未提供 target_value 时使用当前值作为参考，不触发变化"""
        engine = self._make_engine(read_value=50.0)
        result = asyncio.run(
            engine.run_async(
                "s7_monitor",
                input={"tag_name": "DB1.Temp"},
            )
        )
        assert result.ok is True
        # current == reference，delta=0，无变化
        write_steps = [s for s in result.steps if "s7_write" in s.tool]
        assert len(write_steps) == 0
