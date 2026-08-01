"""
全链路端到端测试 — Orchestrator API → 编排引擎 → Mock MCP。

默认离线套件，不依赖真实 MCP 子进程。
使用 orchestrator/api.py 独立 TestClient，无 backend conftest 依赖。
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


# ============================================================================
# helpers
# ============================================================================

def _make_engine(**kwargs):
    from orchestrator.core import WorkflowResult, StepResult

    steps = kwargs.pop("steps", None)
    ok = kwargs.pop("ok", True)
    error = kwargs.pop("error", "")
    wf_name = kwargs.pop("wf_name", "test_wf")
    wf_list = kwargs.pop("workflow_list", [wf_name])

    if steps is None:
        steps = [
            StepResult(tool="tia-mcp.create_ladder_block", ok=True,
                       data={"blockName": "TestBlock", "networks": 3}, duration_ms=10.0),
            StepResult(tool="tia-mcp.call_fb_in_ob1", ok=True,
                       data={"fb_names": ["TestBlock"]}, duration_ms=5.0),
            StepResult(tool="plc-mcp-bridge.plc_compile_project", ok=True,
                       data={"ok": True, "errors": 0}, duration_ms=20.0),
            StepResult(tool="plc-mcp-bridge.plc_download_project", ok=True,
                       data={"ok": True}, duration_ms=15.0),
            StepResult(tool="plc-mcp-bridge.s7_connect", ok=True,
                       data="connected", duration_ms=3.0),
            StepResult(tool="plc-mcp-bridge.s7_read", ok=True,
                       data={"address": "M0.0", "value": False}, duration_ms=2.0),
            StepResult(tool="plc-mcp-bridge.s7_disconnect", ok=True,
                       data="disconnected", duration_ms=1.0),
        ]

    result = WorkflowResult(
        workflow_name=wf_name, ok=ok, steps=steps, error=error,
        total_duration_ms=kwargs.pop("total_ms", 56.0),
    )

    engine = MagicMock()
    engine.list_workflows.return_value = wf_list
    engine.run_async = AsyncMock(return_value=result)
    return engine, result


@contextmanager
def _mock_bootstrap():
    with (
        patch("orchestrator.api.bootstrap", new_callable=AsyncMock) as b,
        patch("orchestrator.api.shutdown", new_callable=AsyncMock) as s,
    ):
        b.return_value = None
        s.return_value = None
        yield


@contextmanager
def _orch_client(engine, monkeypatch):
    """创建 orchestrator 独立 API 的 TestClient。"""
    monkeypatch.setenv("LOCAL_API_TOKEN", "orch-test-token")

    mock_lock = MagicMock()
    with _mock_bootstrap(), \
         patch("orchestrator.api.get_engine", return_value=engine), \
         patch("orchestrator.api.get_registry", return_value=MagicMock()), \
         patch("orchestrator.api.McpOwnerLock", return_value=mock_lock):
        from orchestrator.api import app
        app.dependency_overrides.clear()
        with TestClient(app, raise_server_exceptions=False) as c:
            c.headers.update({"X-Local-Api-Token": "orch-test-token"})
            yield c


# ============================================================================
# 测试
# ============================================================================

class TestHealth:
    def test_ok(self, monkeypatch):
        engine, _ = _make_engine()
        with _orch_client(engine, monkeypatch) as c:
            res = c.get("/health")
            assert res.status_code == 200
            assert res.json()["status"] == "ok"


class TestWorkflowRun:
    def test_success(self, monkeypatch):
        from orchestrator.core import WorkflowResult, StepResult

        result = WorkflowResult(
            workflow_name="s7_monitor", ok=True,
            steps=[StepResult(tool="p.s7_read", ok=True, data={"v": 100}, duration_ms=2.0)],
            total_duration_ms=5.0,
        )
        engine = MagicMock()
        engine.list_workflows.return_value = ["s7_monitor"]
        engine.run_async = AsyncMock(return_value=result)

        with _orch_client(engine, monkeypatch) as c:
            res = c.post("/workflows/s7_monitor/run", json={"input": {}})
            assert res.status_code == 200
            assert res.json()["ok"] is True

    def test_404(self, monkeypatch):
        engine, _ = _make_engine()
        with _orch_client(engine, monkeypatch) as c:
            res = c.post("/workflows/no_such/run", json={"input": {}})
            assert res.status_code == 404

    def test_actor_not_forgeable(self, monkeypatch):
        from orchestrator.core import WorkflowResult

        observed = {}

        async def _capture(name, *, input=None, **kw):
            observed["input"] = input
            return WorkflowResult(workflow_name=name, ok=True, steps=[], total_duration_ms=1.0)

        engine = MagicMock()
        engine.list_workflows.return_value = ["test_wf"]
        engine.run_async = _capture

        with _orch_client(engine, monkeypatch) as c:
            res = c.post(
                "/workflows/test_wf/run",
                json={"input": {"authenticated_operator": "forged"}},
            )
            assert res.status_code == 200
            # 路由层覆盖了自报的 forged 身份为真实 local-session
            received = observed.get("input", {})
            assert received.get("authenticated_operator", "").startswith("local-session:")
            assert "forged" not in received.get("authenticated_operator", "")

    def test_failed_workflow(self, monkeypatch):
        from orchestrator.core import WorkflowResult

        result = WorkflowResult(
            workflow_name="bad", ok=False,
            error="编译失败: 2 errors", total_duration_ms=56.0,
        )
        engine = MagicMock()
        engine.list_workflows.return_value = ["bad"]
        engine.run_async = AsyncMock(return_value=result)

        with _orch_client(engine, monkeypatch) as c:
            res = c.post("/workflows/bad/run", json={"input": {}})
            assert res.status_code == 200
            assert res.json()["ok"] is False
            assert "编译失败" in res.json()["error"]

    def test_7_step_workflow(self, monkeypatch):
        engine, _ = _make_engine(wf_name="full_pipeline")
        with _orch_client(engine, monkeypatch) as c:
            res = c.post("/workflows/full_pipeline/run", json={"input": {}})
            assert res.status_code == 200
            data = res.json()
            assert data["ok"] is True
            assert len(data["steps"]) == 7
            assert data["steps"][0]["tool"] == "tia-mcp.create_ladder_block"


class TestListEndpoints:
    def test_workflows(self, monkeypatch):
        engine, _ = _make_engine()
        with _orch_client(engine, monkeypatch) as c:
            res = c.get("/workflows")
            assert res.status_code == 200

    def test_tools(self, monkeypatch):
        engine, _ = _make_engine()
        with _orch_client(engine, monkeypatch) as c:
            res = c.get("/tools")
            assert res.status_code == 200

    def test_servers(self, monkeypatch):
        engine, _ = _make_engine()
        from orchestrator.registry import ServerInfo

        mock_registry = MagicMock()
        mock_registry.list_servers.return_value = []
        mock_registry.server_count.return_value = 0
        mock_registry.tool_count.return_value = 0

        monkeypatch.setenv("LOCAL_API_TOKEN", "orch-test-token")
        mock_lock = MagicMock()
        with _mock_bootstrap(), \
             patch("orchestrator.api.get_engine", return_value=engine), \
             patch("orchestrator.api.get_registry", return_value=mock_registry), \
             patch("orchestrator.api.McpOwnerLock", return_value=mock_lock):
            from orchestrator.api import app
            app.dependency_overrides.clear()
            with TestClient(app, raise_server_exceptions=False) as c:
                c.headers.update({"X-Local-Api-Token": "orch-test-token"})
                res = c.get("/servers")
                assert res.status_code == 200

    def test_auth_required(self, monkeypatch):
        engine, _ = _make_engine()
        with _orch_client(engine, monkeypatch) as c:
            c.headers.pop("X-Local-Api-Token", None)
            res = c.post("/workflows/test_wf/run", json={"input": {}})
            assert res.status_code == 401
