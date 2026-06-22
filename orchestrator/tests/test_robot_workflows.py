"""
测试机器人工作流 — robot_pick_place 和 robot_monitor。

覆盖:
- 工作流注册（2 个）
- robot_pick_place 正常执行（mock 模式）
- robot_pick_place 急停中止
- robot_monitor 状态报告
- 步骤顺序验证
- __init__.py 集成注册
"""
import asyncio
import pytest

from orchestrator.core import OrchestratorEngine
from orchestrator.workflows.robot_pick_place import register_robot_pick_place_workflow
from orchestrator.workflows.robot_monitor import register_robot_monitor_workflow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_status(
    estop: bool = False,
    connection: str = "connected (snap7)",
    position: str = "retracted",
) -> dict:
    """构造 robot-mcp.get_status mock 返回值"""
    backend = "none"
    if "opcua" in connection:
        backend = "opcua"
    elif "snap7" in connection:
        backend = "snap7"

    return {
        "connection": connection,
        "backend": backend,
        "plc_ip": "192.168.0.1",
        "scene": "Pick & Place (Basic)",
        "sensors": {
            "sensor_estop": estop,
            "sensor_moving_x": position == "extended",
        },
        "estimated_position": position,
        "emergency_stop": estop,
    }


def _make_engine(
    estop: bool = False,
    connection: str = "connected (snap7)",
    position: str = "retracted",
) -> OrchestratorEngine:
    """创建带 mock 工具的引擎"""
    engine = OrchestratorEngine()
    register_robot_pick_place_workflow(engine)
    register_robot_monitor_workflow(engine)

    engine.register_mock(
        "robot-mcp.get_status",
        lambda **kw: _make_status(estop=estop, connection=connection, position=position),
    )
    engine.register_mock(
        "robot-mcp.go_home",
        lambda **kw: {"status": "ok", "position": "home"},
    )
    engine.register_mock(
        "robot-mcp.control_conveyor",
        lambda direction="stop", **kw: {"status": "ok", "direction": direction},
    )
    engine.register_mock(
        "robot-mcp.pick_item",
        lambda **kw: {"status": "ok", "action": "pick", "message": "物料已抓取"},
    )
    engine.register_mock(
        "robot-mcp.place_item",
        lambda **kw: {"status": "ok", "action": "place", "message": "物料已放置"},
    )
    return engine


# ---------------------------------------------------------------------------
# 工作流注册测试
# ---------------------------------------------------------------------------

class TestWorkflowRegistration:

    def test_register_robot_pick_place(self):
        engine = OrchestratorEngine()
        register_robot_pick_place_workflow(engine)
        assert "robot_pick_place" in engine.list_workflows()

    def test_register_robot_monitor(self):
        engine = OrchestratorEngine()
        register_robot_monitor_workflow(engine)
        assert "robot_monitor" in engine.list_workflows()


# ---------------------------------------------------------------------------
# robot_pick_place 测试
# ---------------------------------------------------------------------------

class TestRobotPickPlace:

    def test_normal_execution(self):
        """正常流程：全部步骤执行成功"""
        engine = _make_engine(estop=False)
        result = asyncio.run(
            engine.run_async("robot_pick_place", input={})
        )
        assert result.ok is True
        assert result.error == ""

    def test_returns_pick_and_place(self):
        """返回结果包含 pick 和 place"""
        engine = _make_engine(estop=False)
        result = asyncio.run(
            engine.run_async("robot_pick_place", input={})
        )
        assert result.ok is True
        # 从 context 步骤数据中验证 pick/place 被调用
        tools_called = [s.tool for s in result.steps]
        assert "robot-mcp.pick_item" in tools_called
        assert "robot-mcp.place_item" in tools_called

    def test_estop_aborts(self):
        """急停触发时立即中止，不执行后续步骤"""
        engine = _make_engine(estop=True)
        result = asyncio.run(
            engine.run_async("robot_pick_place", input={})
        )
        # 工作流本身 ok（没有异常），但只执行了 get_status
        assert result.ok is True
        tools_called = [s.tool for s in result.steps]
        assert "robot-mcp.get_status" in tools_called
        # 不应执行 go_home / pick / place
        assert "robot-mcp.go_home" not in tools_called
        assert "robot-mcp.pick_item" not in tools_called
        assert "robot-mcp.place_item" not in tools_called

    def test_step_order(self):
        """步骤执行顺序：get_status → go_home → conveyor(entry) → pick → conveyor(exit) → place"""
        engine = _make_engine(estop=False)
        result = asyncio.run(
            engine.run_async("robot_pick_place", input={})
        )
        tools_called = [s.tool for s in result.steps]
        expected = [
            "robot-mcp.get_status",
            "robot-mcp.go_home",
            "robot-mcp.control_conveyor",
            "robot-mcp.pick_item",
            "robot-mcp.control_conveyor",
            "robot-mcp.place_item",
        ]
        assert tools_called == expected

    def test_conveyor_directions(self):
        """传送带方向：第一次 entry，第二次 exit"""
        engine = _make_engine(estop=False)

        conveyor_calls = []

        def mock_conveyor(direction="stop", **kw):
            conveyor_calls.append(direction)
            return {"status": "ok", "direction": direction}

        engine.register_mock("robot-mcp.control_conveyor", mock_conveyor)

        asyncio.run(engine.run_async("robot_pick_place", input={}))
        assert conveyor_calls == ["entry", "exit"]

    def test_total_step_count(self):
        """正常模式下共 6 个步骤"""
        engine = _make_engine(estop=False)
        result = asyncio.run(
            engine.run_async("robot_pick_place", input={})
        )
        assert len(result.steps) == 6

    def test_estop_step_count(self):
        """急停模式下仅 1 个步骤（get_status）"""
        engine = _make_engine(estop=True)
        result = asyncio.run(
            engine.run_async("robot_pick_place", input={})
        )
        assert len(result.steps) == 1


# ---------------------------------------------------------------------------
# robot_monitor 测试
# ---------------------------------------------------------------------------

class TestRobotMonitor:

    def test_status_report_fields(self):
        """状态报告包含所有预期字段"""
        engine = _make_engine(estop=False, position="retracted")
        result = asyncio.run(
            engine.run_async("robot_monitor", input={})
        )
        assert result.ok is True
        assert len(result.steps) == 1
        assert result.steps[0].tool == "robot-mcp.get_status"

    def test_status_report_values(self):
        """状态报告值与 mock 数据一致"""
        engine = _make_engine(
            estop=False,
            connection="connected (opcua)",
            position="extended",
        )
        # 直接调用工作流函数获取返回值
        ctx = engine._build_context({})
        wf = engine.get_workflow("robot_monitor")
        report = asyncio.run(wf(ctx))
        assert report["connection"] == "connected (opcua)"
        assert report["emergency_stop"] is False
        assert report["arm_position"] == "extended"
        assert report["backend"] == "opcua"
        assert report["plc_ip"] == "192.168.0.1"
        assert report["scene"] == "Pick & Place (Basic)"

    def test_estop_status_reported(self):
        """急停状态正确反映在报告中"""
        engine = _make_engine(estop=True)
        ctx = engine._build_context({})
        wf = engine.get_workflow("robot_monitor")
        report = asyncio.run(wf(ctx))
        assert report["emergency_stop"] is True


# ---------------------------------------------------------------------------
# __init__.py 集成注册测试
# ---------------------------------------------------------------------------

class TestInitRegistration:

    def test_register_all_includes_robot_workflows(self):
        """register_all_workflows 注册了机器人工作流"""
        from orchestrator.workflows import register_all_workflows

        engine = OrchestratorEngine()
        register_all_workflows(engine)
        workflows = engine.list_workflows()
        assert "robot_pick_place" in workflows
        assert "robot_monitor" in workflows
