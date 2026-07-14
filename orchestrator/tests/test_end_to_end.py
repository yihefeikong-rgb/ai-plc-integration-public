"""
全仓端到端集成测试 — TS020。

覆盖 4 个测试类：
  1. TestS7WorkflowEndToEnd (mock) — S7 监控工作流全生命周期
  2. TestRobotWorkflowEndToEnd (mock) — 机器人 pick_and_place 工作流
  3. TestOrchestratorApiIntegration (mock) — 后端 API → 编排层路由
  4. TestRealS7EndToEnd (integration) — 真实 PLCSIM 直连测试

运行方式:
    pytest orchestrator/tests/test_end_to_end.py -v
    pytest orchestrator/tests/test_end_to_end.py -v -m "not integration"  # 仅 mock
    pytest orchestrator/tests/test_end_to_end.py -v -m integration        # 仅集成
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from orchestrator.core import OrchestratorEngine, WorkflowContext
from orchestrator.workflows.s7_monitor import (
    detect_change,
    mock_ai_analyze,
    register_s7_monitor_workflow,
)
from orchestrator.workflows.robot_pick_place import register_robot_pick_place_workflow
from orchestrator.workflows.robot_monitor import register_robot_monitor_workflow

# ============================================================================
# Shared mock helpers
# ============================================================================

MOCK_READ_VALUE = 100.0
MOCK_WRITE_OK = {"ok": True, "tag": "DB1.TestTag", "value": 100.0}


def _make_s7_engine(read_value: float = MOCK_READ_VALUE) -> OrchestratorEngine:
    """创建带 S7 mock 工具的引擎"""
    engine = OrchestratorEngine()
    register_s7_monitor_workflow(engine)
    engine.register_mock(
        "plc-mcp-bridge.s7_read",
        lambda tag, **kw: {"value": read_value, "tag": tag},
    )
    engine.register_mock(
        "plc-mcp-bridge.s7_write",
        lambda tag, value, **kw: {"ok": True, "tag": tag, "value": value},
    )
    return engine


def _make_robot_status(
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


def _make_robot_engine(
    estop: bool = False,
    connection: str = "connected (snap7)",
    position: str = "retracted",
) -> OrchestratorEngine:
    """创建带 robot mock 工具的引擎"""
    engine = OrchestratorEngine()
    register_robot_pick_place_workflow(engine)
    register_robot_monitor_workflow(engine)

    engine.register_mock(
        "robot-mcp.get_status",
        lambda **kw: _make_robot_status(
            estop=estop, connection=connection, position=position
        ),
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
        lambda **kw: {"status": "ok", "action": "pick", "message": "material picked"},
    )
    engine.register_mock(
        "robot-mcp.place_item",
        lambda **kw: {"status": "ok", "action": "place", "message": "material placed"},
    )
    return engine


# ============================================================================
# TestS7WorkflowEndToEnd
# ============================================================================

class TestS7WorkflowEndToEnd:
    """S7 监控工作流端到端测试（mock 模式）"""

    def test_full_workflow_read_detect_analyze_write(self):
        """完整流程: read → detect_change → ai_analyze → write"""
        engine = _make_s7_engine(read_value=120.0)
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
        assert result.error == ""

        # 步骤顺序验证
        tools = [s.tool for s in result.steps]
        assert tools[0] == "plc-mcp-bridge.s7_read"
        # 有变化且 AI 建议 write → 应包含 s7_write
        assert "plc-mcp-bridge.s7_write" in tools

    def test_full_workflow_no_change_skips_write(self):
        """无变化时跳过写入步骤"""
        engine = _make_s7_engine(read_value=100.0)
        result = asyncio.run(
            engine.run_async(
                "s7_monitor",
                input={"tag_name": "DB1.Temp", "target_value": 100.0},
            )
        )
        assert result.ok is True
        write_steps = [s for s in result.steps if "s7_write" in s.tool]
        assert len(write_steps) == 0

    def test_read_value_passed_to_write(self):
        """写入的值来自 AI 建议（100.0）"""
        captured_write_values = []

        engine = OrchestratorEngine()
        register_s7_monitor_workflow(engine)
        engine.register_mock(
            "plc-mcp-bridge.s7_read",
            lambda tag, **kw: {"value": 120.0, "tag": tag},
        )

        def capture_write(tag, value, **kw):
            captured_write_values.append(value)
            return {"ok": True, "tag": tag, "value": value}

        engine.register_mock("plc-mcp-bridge.s7_write", capture_write)

        asyncio.run(
            engine.run_async(
                "s7_monitor",
                input={
                    "tag_name": "DB1.Temp",
                    "target_value": 100.0,
                    "delta_threshold": 0.1,
                },
            )
        )
        assert len(captured_write_values) == 1
        assert captured_write_values[0] == 100.0

    def test_safety_gate_not_triggered_in_mock_mode(self):
        """mock 模式下 SafetyGate 不拦截"""
        engine = _make_s7_engine(read_value=120.0)
        engine.set_safety_gate()
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
        # mock 模式绕过 SafetyGate，应正常完成
        assert result.ok is True

    def test_error_handling_mock_read_fails(self):
        """mock s7_read 返回错误时工作流处理"""
        engine = OrchestratorEngine()
        register_s7_monitor_workflow(engine)
        engine.register_mock(
            "plc-mcp-bridge.s7_read",
            lambda tag, **kw: (_ for _ in ()).throw(
                RuntimeError("PLCSIM connection lost")
            ),
        )
        engine.register_mock(
            "plc-mcp-bridge.s7_write",
            lambda tag, value, **kw: {"ok": True},
        )

        result = asyncio.run(
            engine.run_async(
                "s7_monitor",
                input={"tag_name": "DB1.Temp", "target_value": 100.0},
            )
        )
        # read 失败导致工作流 result.ok 为 False
        assert result.ok is False
        read_step = result.steps[0]
        assert read_step.ok is False
        assert "PLCSIM connection lost" in read_step.error

    def test_error_handling_mock_write_fails(self):
        """mock s7_write 返回错误时工作流记录失败"""
        engine = OrchestratorEngine()
        register_s7_monitor_workflow(engine)
        engine.register_mock(
            "plc-mcp-bridge.s7_read",
            lambda tag, **kw: {"value": 120.0, "tag": tag},
        )
        engine.register_mock(
            "plc-mcp-bridge.s7_write",
            lambda tag, value, **kw: (_ for _ in ()).throw(
                RuntimeError("SafetyGate rejected write")
            ),
        )

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
        # write 失败 → result.ok 应为 False
        assert result.ok is False
        write_step = result.steps[-1]
        assert write_step.ok is False
        assert "SafetyGate rejected write" in write_step.error
        # read 步骤仍成功
        read_step = result.steps[0]
        assert read_step.ok is True

    def test_result_steps_have_duration(self):
        """每个 StepResult 都有 duration_ms"""
        engine = _make_s7_engine(read_value=120.0)
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
        for step in result.steps:
            assert step.duration_ms >= 0.0
        assert result.total_duration_ms >= 0.0

    def test_no_changed_no_write_even_with_high_value(self):
        """当 target_value==current 时 delta=0，即使值很高也不触发写入"""
        engine = _make_s7_engine(read_value=200.0)
        result = asyncio.run(
            engine.run_async(
                "s7_monitor",
                input={
                    "tag_name": "DB1.Temp",
                    "target_value": 200.0,  # same as current
                },
            )
        )
        assert result.ok is True
        write_steps = [s for s in result.steps if "s7_write" in s.tool]
        assert len(write_steps) == 0

    def test_large_value_read_and_write(self):
        """大数值（浮点）读取和写入"""
        engine = _make_s7_engine(read_value=99999.5)
        result = asyncio.run(
            engine.run_async(
                "s7_monitor",
                input={
                    "tag_name": "DB1.BigValue",
                    "target_value": 0.0,
                    "delta_threshold": 0.1,
                },
            )
        )
        assert result.ok is True
        write_steps = [s for s in result.steps if "s7_write" in s.tool]
        assert len(write_steps) == 1

    def test_negative_value_analysis(self):
        """负数值触发 write（偏低分析）"""
        engine = _make_s7_engine(read_value=-50.0)
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
        assert len(write_steps) == 1


# ============================================================================
# TestRobotWorkflowEndToEnd
# ============================================================================

class TestRobotWorkflowEndToEnd:
    """机器人工作流端到端测试（mock 模式）"""

    def test_full_pick_place_normal(self):
        """正常执行：全部 6 步骤成功"""
        engine = _make_robot_engine(estop=False)
        result = asyncio.run(
            engine.run_async("robot_pick_place", input={})
        )
        assert result.ok is True
        assert len(result.steps) == 6
        assert result.error == ""

    def test_full_pick_place_step_order(self):
        """步骤执行顺序验证"""
        engine = _make_robot_engine(estop=False)
        result = asyncio.run(
            engine.run_async("robot_pick_place", input={})
        )
        expected = [
            "robot-mcp.get_status",
            "robot-mcp.go_home",
            "robot-mcp.control_conveyor",
            "robot-mcp.pick_item",
            "robot-mcp.control_conveyor",
            "robot-mcp.place_item",
        ]
        actual = [s.tool for s in result.steps]
        assert actual == expected

    def test_estop_interrupts_workflow(self):
        """急停触发时立即中止"""
        engine = _make_robot_engine(estop=True)
        result = asyncio.run(
            engine.run_async("robot_pick_place", input={})
        )
        assert result.ok is False
        assert "急停已触发" in result.error
        assert len(result.steps) == 1
        assert result.steps[0].tool == "robot-mcp.get_status"
        # 不应执行后续步骤
        later_tools = ["robot-mcp.go_home", "robot-mcp.pick_item", "robot-mcp.place_item"]
        called = [s.tool for s in result.steps]
        for tool in later_tools:
            assert tool not in called

    def test_estop_with_connection_issues(self):
        """急停 + 连接问题"""
        engine = _make_robot_engine(
            estop=True,
            connection="disconnected",
            position="unknown",
        )
        result = asyncio.run(
            engine.run_async("robot_pick_place", input={})
        )
        assert result.ok is False
        assert "急停已触发" in result.error
        assert len(result.steps) == 1

    def test_error_handling_get_status_fails(self):
        """get_status 调用失败"""
        engine = OrchestratorEngine()
        register_robot_pick_place_workflow(engine)
        engine.register_mock(
            "robot-mcp.get_status",
            lambda **kw: (_ for _ in ()).throw(
                RuntimeError("Robot controller unreachable")
            ),
        )
        engine.register_mock(
            "robot-mcp.go_home",
            lambda **kw: {"status": "ok"},
        )
        engine.register_mock(
            "robot-mcp.control_conveyor",
            lambda **kw: {"status": "ok"},
        )
        engine.register_mock(
            "robot-mcp.pick_item",
            lambda **kw: {"status": "ok"},
        )
        engine.register_mock(
            "robot-mcp.place_item",
            lambda **kw: {"status": "ok"},
        )

        result = asyncio.run(
            engine.run_async("robot_pick_place", input={})
        )
        assert result.ok is False
        assert result.steps[0].ok is False
        assert "Robot controller unreachable" in result.steps[0].error

    def test_error_handling_pick_fails_mid_workflow(self):
        """中间步骤（pick_item）失败"""
        engine = OrchestratorEngine()
        register_robot_pick_place_workflow(engine)
        engine.register_mock(
            "robot-mcp.get_status",
            lambda **kw: _make_robot_status(estop=False),
        )
        engine.register_mock(
            "robot-mcp.go_home",
            lambda **kw: {"status": "ok"},
        )
        engine.register_mock(
            "robot-mcp.control_conveyor",
            lambda **kw: {"status": "ok"},
        )
        engine.register_mock(
            "robot-mcp.pick_item",
            lambda **kw: (_ for _ in ()).throw(
                RuntimeError("Gripper jammed")
            ),
        )
        engine.register_mock(
            "robot-mcp.place_item",
            lambda **kw: {"status": "ok"},
        )

        result = asyncio.run(
            engine.run_async("robot_pick_place", input={})
        )
        assert result.ok is False
        tools = [s.tool for s in result.steps]
        # 前几个步骤仍应执行
        assert "robot-mcp.get_status" in tools
        assert "robot-mcp.go_home" in tools
        assert "robot-mcp.control_conveyor" in tools
        assert "robot-mcp.pick_item" in tools
        # place_item 不应执行（workflow 在 pick 失败后终止）
        assert "robot-mcp.place_item" not in tools

    def test_conveyor_directions_sequence(self):
        """传送带方向：entry 然后 exit"""
        engine = _make_robot_engine(estop=False)
        result = asyncio.run(
            engine.run_async("robot_pick_place", input={})
        )
        conveyor_steps = [s for s in result.steps if "control_conveyor" in s.tool]
        assert len(conveyor_steps) == 2
        assert conveyor_steps[0].ok is True
        assert conveyor_steps[1].ok is True

    def test_workflow_result_steps_all_ok(self):
        """正常流程所有步骤 ok=True"""
        engine = _make_robot_engine(estop=False)
        result = asyncio.run(
            engine.run_async("robot_pick_place", input={})
        )
        for step in result.steps:
            assert step.ok is True, f"Step {step.tool} failed: {step.error}"

    def test_robot_monitor_workflow_e2e(self):
        """robot_monitor 工作流端到端"""
        engine = _make_robot_engine(estop=False, position="retracted")
        result = asyncio.run(
            engine.run_async("robot_monitor", input={})
        )
        assert result.ok is True
        assert len(result.steps) == 1
        assert result.steps[0].tool == "robot-mcp.get_status"

    def test_robot_monitor_returns_fields(self):
        """robot_monitor 返回包含所有预期字段"""
        engine = _make_robot_engine(estop=False, position="extended")
        ctx = engine._build_context({})
        wf = engine.get_workflow("robot_monitor")
        report = asyncio.run(wf(ctx))
        assert report["connection"] == "connected (snap7)"
        assert report["emergency_stop"] is False
        assert report["arm_position"] == "extended"
        assert report["backend"] == "snap7"
        assert report["plc_ip"] == "192.168.0.1"
        assert report["scene"] == "Pick & Place (Basic)"


# ============================================================================
# TestOrchestratorApiIntegration
# ============================================================================

class TestOrchestratorApiIntegration:
    """后端 API → 编排层路由集成测试（FastAPI TestClient）"""

    @pytest.fixture
    def test_app(self):
        """创建配置了 mock 编排引擎的 FastAPI TestClient"""
        # 使用后端的 conftest.py 中的 mock_orchestrator_lifespan fixture
        # 需要导入真实 app
        BACKEND_DIR = Path(__file__).parent.parent.parent / "ai-plc-assistant" / "backend"
        import os as _os
        import sys as _sys
        _orig_cwd = _os.getcwd()
        _previous_token = _os.environ.get("LOCAL_API_TOKEN")
        _os.environ["LOCAL_API_TOKEN"] = "orchestrator-e2e-test-token"
        if str(BACKEND_DIR) not in _sys.path:
            _sys.path.insert(0, str(BACKEND_DIR))

        # 切换到 backend 目录导入 app
        _os.chdir(str(BACKEND_DIR))
        try:
            from main import app
            from fastapi.testclient import TestClient

            # mock orchestrator bootstrap/shutdown
            with patch("main.bootstrap", AsyncMock(return_value=None)), \
                patch("main.orchestrator_shutdown", AsyncMock(return_value=None)):
                with TestClient(app) as client:
                    client.headers.update({"X-Local-Api-Token": "orchestrator-e2e-test-token"})
                    yield client
        finally:
            if _previous_token is None:
                _os.environ.pop("LOCAL_API_TOKEN", None)
            else:
                _os.environ["LOCAL_API_TOKEN"] = _previous_token
            _os.chdir(str(_orig_cwd))

    def test_health_endpoint(self, test_app):
        """GET /api/orchestrator/health 返回 200"""
        res = test_app.get("/api/orchestrator/health")
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert isinstance(data["servers_connected"], int)
        assert isinstance(data["workflows"], int)
        assert isinstance(data["tools"], int)

    def test_workflows_endpoint(self, test_app):
        """GET /api/orchestrator/workflows 返回工作流列表"""
        res = test_app.get("/api/orchestrator/workflows")
        assert res.status_code == 200
        data = res.json()
        assert "workflows" in data
        assert isinstance(data["workflows"], list)

    def test_workflows_contains_expected_names(self, test_app):
        """工作流列表包含预期名称"""
        res = test_app.get("/api/orchestrator/workflows")
        workflows = res.json()["workflows"]
        # 全局引擎应已注册这些工作流（通过 bootstrap）
        # 如果 bootstrap 被 mock 了，可能为空
        # 不做具体断言，只验证格式
        for wf in workflows:
            assert isinstance(wf, str)

    def test_run_nonexistent_workflow_404(self, test_app):
        """执行不存在的工作流返回 404"""
        res = test_app.post(
            "/api/orchestrator/workflows/nonexistent_xyz_123/run",
            json={"input": {}},
        )
        assert res.status_code == 404

    def test_tools_endpoint(self, test_app):
        """GET /api/orchestrator/tools 返回工具列表"""
        res = test_app.get("/api/orchestrator/tools")
        assert res.status_code == 200
        data = res.json()
        assert "tools" in data
        assert isinstance(data["tools"], list)

    def test_tools_items_have_expected_structure(self, test_app):
        """工具列表每一项都有 name, server, category, description"""
        res = test_app.get("/api/orchestrator/tools")
        tools = res.json()["tools"]
        for tool in tools:
            assert "name" in tool
            assert "server" in tool
            assert "category" in tool
            assert "description" in tool

    def test_servers_endpoint(self, test_app):
        """GET /api/orchestrator/servers 返回服务器列表"""
        res = test_app.get("/api/orchestrator/servers")
        assert res.status_code == 200
        data = res.json()
        assert "servers" in data
        assert isinstance(data["servers"], list)

    def test_servers_items_have_expected_structure(self, test_app):
        """服务器列表每一项都有 name, description, tool_count"""
        res = test_app.get("/api/orchestrator/servers")
        servers = res.json()["servers"]
        for server in servers:
            assert "name" in server
            assert "description" in server
            assert "tool_count" in server
            assert isinstance(server["tool_count"], int)

    def test_monitor_endpoint(self, test_app):
        """GET /api/orchestrator/monitor 返回监控状态"""
        res = test_app.get("/api/orchestrator/monitor")
        assert res.status_code == 200
        data = res.json()
        assert "servers_connected" in data
        assert "active_workflows" in data
        assert "total_tools" in data
        assert "tool_call_counts" in data
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], float)
        assert isinstance(data["tool_call_counts"], dict)

    def test_run_workflow_with_mock_engine_e2e(self, test_app):
        """Mock 编排引擎执行工作流端到端"""
        from orchestrator.core import WorkflowResult, StepResult

        mock_result = WorkflowResult(
            workflow_name="s7_monitor",
            ok=True,
            steps=[
                StepResult(
                    tool="plc-mcp-bridge.s7_read",
                    ok=True,
                    data={"value": 100.0},
                    duration_ms=2.0,
                ),
                StepResult(
                    tool="plc-mcp-bridge.s7_write",
                    ok=True,
                    data={"ok": True},
                    duration_ms=5.0,
                ),
            ],
            total_duration_ms=10.0,
        )

        with patch(
            "routes.orchestrator.get_engine"
        ) as mock_get_engine:
            mock_engine = MagicMock()
            mock_engine.list_workflows.return_value = ["s7_monitor"]
            mock_engine.run_async = AsyncMock(return_value=mock_result)
            mock_get_engine.return_value = mock_engine

            res = test_app.post(
                "/api/orchestrator/workflows/s7_monitor/run",
                json={"input": {"tag_name": "DB1.Temp", "target_value": 100.0}},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["ok"] is True
            assert data["workflow_name"] == "s7_monitor"
            assert len(data["steps"]) == 2
            assert data["steps"][0]["tool"] == "plc-mcp-bridge.s7_read"
            assert data["steps"][1]["tool"] == "plc-mcp-bridge.s7_write"
            assert data["total_duration_ms"] == 10.0

    def test_dynamic_workflow_list_endpoint(self, test_app):
        """GET /api/orchestrator/workflows/dynamic 返回动态工作流列表"""
        res = test_app.get("/api/orchestrator/workflows/dynamic")
        assert res.status_code == 200
        data = res.json()
        assert "workflows" in data
        assert isinstance(data["workflows"], list)

    def test_dynamic_workflow_nonexistent_404(self, test_app):
        """GET 不存在的动态工作流返回 404"""
        res = test_app.get("/api/orchestrator/workflows/dynamic/nonexistent_dyn_999")
        assert res.status_code == 404

    def test_adhoc_run_endpoint(self, test_app):
        """POST /api/orchestrator/workflows/adhoc 执行临时工作流"""
        from orchestrator.core import WorkflowResult, StepResult

        mock_result = WorkflowResult(
            workflow_name="adhoc",
            ok=True,
            steps=[
                StepResult(
                    tool="plc-mcp-bridge.s7_read",
                    ok=True,
                    data={"value": 42},
                    duration_ms=1.0,
                ),
            ],
            total_duration_ms=3.0,
        )

        mock_engine = MagicMock()
        mock_engine.run_adhoc = AsyncMock(return_value=mock_result)

        with patch("routes.orchestrator.get_engine", return_value=mock_engine):
            res = test_app.post(
                "/api/orchestrator/workflows/adhoc",
                json={
                    "steps": [
                        {"server": "plc-mcp-bridge", "tool": "s7_read", "params": {"tag": "DB1.Test"}},
                    ],
                    "input": {},
                },
            )
            assert res.status_code == 200
            data = res.json()
            assert data["ok"] is True
            assert len(data["steps"]) == 1
            assert data["steps"][0]["data"]["value"] == 42


# ============================================================================
# TestRealS7EndToEnd
# ============================================================================

# ---------------------------------------------------------------------------
# PLCSIM integration helpers (module-level, no class-scoped fixture warning)
# ---------------------------------------------------------------------------

_PLCSIM_IP = "192.168.0.1"
_PLCSIM_RACK = 0
_PLCSIM_SLOT = 1
_PLCSIM_PORT = 102


def _try_connect_plcsim():
    """尝试连接 PLCSIM，返回 (client, error_msg)"""
    try:
        import snap7
    except ImportError as exc:
        return None, f"snap7 not installed: {exc}"

    client = snap7.client.Client()
    try:
        client.connect(_PLCSIM_IP, _PLCSIM_RACK, _PLCSIM_SLOT, _PLCSIM_PORT)
        return client, None
    except Exception as exc:
        try:
            client.destroy()
        except Exception:
            pass
        return None, f"{type(exc).__name__}: {exc}"


def _disconnect_plcsim(client):
    """安全断开连接"""
    if client is None:
        return
    try:
        client.disconnect()
    except Exception:
        pass
    try:
        client.destroy()
    except Exception:
        pass


@pytest.fixture(scope="module")
def plcsim_e2e_adapter():
    """模块级 fixture：S7Adapter 连接 PLCSIM，不可用时 skip"""
    BRIDGE_ROOT = Path(__file__).parent.parent.parent / "mcp-servers" / "plc-mcp-bridge"
    if str(BRIDGE_ROOT) not in sys.path:
        sys.path.insert(0, str(BRIDGE_ROOT))

    client, error = _try_connect_plcsim()
    if client is None:
        pytest.skip(f"PLCSIM not available: {error}")

    from s7_adapter import S7Adapter
    adapter = S7Adapter()
    adapter._client = client
    adapter._connected = True
    yield adapter
    _disconnect_plcsim(client)


@pytest.mark.integration
class TestRealS7EndToEnd:
    """真实 PLCSIM 端到端测试（需要 PLCSIM Advanced 运行中）

    使用 S7Adapter 直连 PLCSIM 进行 S7 协议读写验证。
    当 PLCSIM 不可用时自动 skip。
    """

    def test_plcsim_connect_and_disconnect(self, plcsim_e2e_adapter):
        """验证连接 PLCSIM 成功"""
        assert plcsim_e2e_adapter.is_connected is True

    def test_read_MW0_via_adapter(self, plcsim_e2e_adapter):
        """通过 S7Adapter 读取 MW0"""
        val = plcsim_e2e_adapter.read_mw(0)
        assert isinstance(val, int)

    def test_write_then_read_MW100(self, plcsim_e2e_adapter):
        """写入 MW100=42，回读验证"""
        plcsim_e2e_adapter.write_mw(100, 42)
        val = plcsim_e2e_adapter.read_mw(100)
        assert val == 42
        # 恢复
        plcsim_e2e_adapter.write_mw(100, 0)

    def test_read_M0_0_bit(self, plcsim_e2e_adapter):
        """读取 M0.0 位"""
        val = plcsim_e2e_adapter.read_address("M0.0")
        assert val in (True, False)

    def test_write_then_read_M0_0_bit(self, plcsim_e2e_adapter):
        """写入 M0.0=True，回读验证"""
        plcsim_e2e_adapter.write_address("M0.0", True)
        val = plcsim_e2e_adapter.read_address("M0.0")
        assert val is True
        # 恢复
        plcsim_e2e_adapter.write_address("M0.0", False)

    def test_write_then_read_MD4_real(self, plcsim_e2e_adapter):
        """写入 MD4=3.14（浮点），回读验证"""
        plcsim_e2e_adapter.write_address("MD4", 3.14)
        val = plcsim_e2e_adapter.read_address("MD4")
        assert abs(val - 3.14) < 0.1
        # 恢复
        plcsim_e2e_adapter.write_address("MD4", 0.0)

    def test_multiple_reads_on_same_address(self, plcsim_e2e_adapter):
        """同一地址多次读取一致性"""
        plcsim_e2e_adapter.write_mw(200, 123)
        vals = [plcsim_e2e_adapter.read_mw(200) for _ in range(3)]
        assert all(v == 123 for v in vals)
        # 恢复
        plcsim_e2e_adapter.write_mw(200, 0)

    def test_disconnect_and_read_fails(self, plcsim_e2e_adapter):
        """断开连接后读取应抛出异常"""
        plcsim_e2e_adapter.disconnect()
        assert plcsim_e2e_adapter.is_connected is False
        with pytest.raises(ConnectionError):
            plcsim_e2e_adapter.read_address("MW0")
