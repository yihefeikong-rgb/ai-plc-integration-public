"""
编排层 HTTP API 测试

使用 FastAPI TestClient 测试所有端点，
mock bootstrap/shutdown 避免真实 MCP 连接。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from orchestrator.core import StepResult, WorkflowResult, get_engine
from orchestrator.registry import ServerInfo, ToolInfo, get_registry


@pytest.fixture(autouse=True)
def _reset_singletons():
    """每个测试前后重置全局单例状态"""
    registry = get_registry()
    engine = get_engine()
    # 记录原始状态以便恢复
    orig_servers = dict(registry._servers)
    orig_tools = dict(registry._tools)
    orig_workflows = dict(engine._workflows)
    yield
    registry._servers = orig_servers
    registry._tools = orig_tools
    engine._workflows = orig_workflows


@pytest.fixture(autouse=True)
def _mock_bootstrap_shutdown():
    """Mock bootstrap/shutdown 避免真实 MCP 连接"""
    with (
        patch("orchestrator.api.bootstrap", new_callable=AsyncMock) as mock_boot,
        patch("orchestrator.api.shutdown", new_callable=AsyncMock) as mock_shut,
    ):
        mock_boot.return_value = None
        mock_shut.return_value = None
        yield mock_boot, mock_shut


@pytest.fixture
def _seed_registry():
    """向注册表注入测试数据"""
    registry = get_registry()
    tool1 = ToolInfo(name="s7_read", description="Read S7 tag", category="s7")
    tool2 = ToolInfo(name="s7_write", description="Write S7 tag", category="s7")
    tool3 = ToolInfo(name="compile_project", description="Compile TIA project", category="tia")
    server = ServerInfo(
        name="plc-mcp-bridge",
        description="PLC MCP Bridge server",
        tools=[tool1, tool2],
    )
    server2 = ServerInfo(
        name="tia-mcp",
        description="TIA Portal MCP server",
        tools=[tool3],
    )
    registry.register_server(server)
    registry.register_server(server2)


@pytest.fixture
def _seed_workflows():
    """向引擎注入测试工作流和 mock 工具"""
    engine = get_engine()
    # 注册 mock 工具，避免需要真实 MCP 连接
    engine.register_mock("tia-mcp.compile_project", lambda **kw: {"compiled": True})
    engine.register_mock("plc-mcp-bridge.s7_read", lambda **kw: {"value": 42})

    @engine.workflow("tia_download")
    def tia_download(ctx):
        ctx.call("tia-mcp.compile_project")
        return {"status": "done"}

    @engine.workflow("s7_monitor")
    def s7_monitor(ctx):
        ctx.call("plc-mcp-bridge.s7_read")
        return {"status": "ok"}


@pytest.fixture
def client(_seed_registry, _seed_workflows):
    """创建 TestClient（触发 lifespan startup/shutdown）"""
    from orchestrator.api import app

    with TestClient(app) as c:
        yield c


# ============================================================================
# 测试用例
# ============================================================================

class TestHealth:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["servers_connected"] == 2
        assert data["workflows"] == 2
        assert data["tools"] == 3

    def test_health_reflects_registry_state(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert data["servers_connected"] >= 0
        assert data["workflows"] >= 0
        assert data["tools"] >= 0


class TestWorkflows:
    def test_list_workflows(self, client):
        resp = client.get("/workflows")
        assert resp.status_code == 200
        wfs = resp.json()["workflows"]
        assert "tia_download" in wfs
        assert "s7_monitor" in wfs

    def test_run_workflow_success(self, client):
        resp = client.post("/workflows/tia_download/run", json={"input": {}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["workflow_name"] == "tia_download"
        assert data["ok"] is True
        assert isinstance(data["steps"], list)
        assert data["total_duration_ms"] >= 0

    def test_run_workflow_with_input(self, client):
        resp = client.post(
            "/workflows/s7_monitor/run",
            json={"input": {"tag": "DB1.DBX0.0"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["workflow_name"] == "s7_monitor"

    def test_run_nonexistent_workflow_returns_404(self, client):
        resp = client.post("/workflows/nonexistent/run", json={"input": {}})
        assert resp.status_code == 404
        assert "未找到工作流" in resp.json()["detail"]


class TestTools:
    def test_list_tools(self, client):
        resp = client.get("/tools")
        assert resp.status_code == 200
        tools = resp.json()["tools"]
        assert len(tools) == 3
        names = {t["name"] for t in tools}
        assert "s7_read" in names
        assert "s7_write" in names
        assert "compile_project" in names

    def test_tool_has_required_fields(self, client):
        resp = client.get("/tools")
        tool = resp.json()["tools"][0]
        assert "name" in tool
        assert "server" in tool
        assert "category" in tool
        assert "description" in tool


class TestServers:
    def test_list_servers(self, client):
        resp = client.get("/servers")
        assert resp.status_code == 200
        servers = resp.json()["servers"]
        assert len(servers) == 2
        names = {s["name"] for s in servers}
        assert "plc-mcp-bridge" in names
        assert "tia-mcp" in names

    def test_server_has_required_fields(self, client):
        resp = client.get("/servers")
        server = resp.json()["servers"][0]
        assert "name" in server
        assert "description" in server
        assert "tool_count" in server
        assert isinstance(server["tool_count"], int)


class TestBootstrapShutdown:
    def test_bootstrap_called_on_startup(self, _mock_bootstrap_shutdown, _seed_registry, _seed_workflows):
        from orchestrator.api import app

        with TestClient(app):
            pass
        _mock_bootstrap_shutdown[0].assert_awaited_once()

    def test_shutdown_called_on_exit(self, _mock_bootstrap_shutdown, _seed_registry, _seed_workflows):
        from orchestrator.api import app

        with TestClient(app):
            pass
        _mock_bootstrap_shutdown[1].assert_awaited_once()
