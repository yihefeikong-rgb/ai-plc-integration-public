"""编排层路由测试 — /api/orchestrator/* 端点。

使用 mock 替代真实 MCP 连接，验证路由层逻辑正确。
"""
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient


# 复用 conftest.py 中的 client fixture（它会 import main.app）
# 但我们需要 mock orchestrator 的 bootstrap 避免真实 MCP 连接。
# conftest.py 中 client fixture 会触发 lifespan，lifespan 中的 bootstrap
# 已经有 try/except 保护，失败只是 warning，所以可以直接使用 client。


class TestOrchestratorHealth:
    def test_health_returns_ok(self, client):
        """GET /api/orchestrator/health 返回基本结构"""
        res = client.get("/api/orchestrator/health")
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert "servers_connected" in data
        assert "workflows" in data
        assert "tools" in data

    def test_health_values_are_ints(self, client):
        """数值字段为整数"""
        res = client.get("/api/orchestrator/health")
        data = res.json()
        assert isinstance(data["servers_connected"], int)
        assert isinstance(data["workflows"], int)
        assert isinstance(data["tools"], int)


class TestOrchestratorWorkflows:
    def test_list_workflows_returns_list(self, client):
        """GET /api/orchestrator/workflows 返回工作流列表"""
        res = client.get("/api/orchestrator/workflows")
        assert res.status_code == 200
        data = res.json()
        assert "workflows" in data
        assert isinstance(data["workflows"], list)

    def test_run_nonexistent_workflow_returns_404(self, client):
        """POST /api/orchestrator/workflows/{name}/run 不存在的工作流返回 404"""
        res = client.post(
            "/api/orchestrator/workflows/nonexistent_workflow/run",
            json={"input": {}},
        )
        assert res.status_code == 404
        assert "未找到工作流" in res.json()["detail"]


class TestOrchestratorTools:
    def test_list_tools_returns_list(self, client):
        """GET /api/orchestrator/tools 返回工具列表"""
        res = client.get("/api/orchestrator/tools")
        assert res.status_code == 200
        data = res.json()
        assert "tools" in data
        assert isinstance(data["tools"], list)


class TestOrchestratorServers:
    def test_list_servers_returns_list(self, client):
        """GET /api/orchestrator/servers 返回服务器列表"""
        res = client.get("/api/orchestrator/servers")
        assert res.status_code == 200
        data = res.json()
        assert "servers" in data
        assert isinstance(data["servers"], list)


class TestOrchestratorMonitor:
    def test_monitor_returns_status(self, client):
        """GET /api/orchestrator/monitor 返回实时状态"""
        res = client.get("/api/orchestrator/monitor")
        assert res.status_code == 200
        data = res.json()
        assert "servers_connected" in data
        assert "active_workflows" in data
        assert "total_tools" in data
        assert "tool_call_counts" in data
        assert "uptime_seconds" in data
        assert isinstance(data["tool_call_counts"], dict)
        assert isinstance(data["uptime_seconds"], float)


class TestOrchestratorWithMocks:
    """使用 mock 测试有注册数据时的端点行为"""

    def test_health_with_mock_registry(self, client):
        """mock 注册表后，health 返回正确的计数"""
        mock_registry = MagicMock()
        mock_registry.server_count.return_value = 2
        mock_registry.tool_count.return_value = 10
        mock_engine = MagicMock()
        mock_engine.list_workflows.return_value = ["wf_a", "wf_b"]

        with patch("routes.orchestrator.get_registry", return_value=mock_registry), \
             patch("routes.orchestrator.get_engine", return_value=mock_engine):
            res = client.get("/api/orchestrator/health")
            assert res.status_code == 200
            data = res.json()
            assert data["servers_connected"] == 2
            assert data["tools"] == 10
            assert data["workflows"] == 2

    def test_list_tools_with_mock_data(self, client):
        """mock 工具列表后，tools 端点返回正确的工具信息"""
        from orchestrator.registry import ToolInfo
        mock_tool = ToolInfo(
            name="s7_read",
            server="plc-mcp-bridge",
            category="s7",
            description="读取 S7 标签",
        )
        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = [mock_tool]

        with patch("routes.orchestrator.get_registry", return_value=mock_registry):
            res = client.get("/api/orchestrator/tools")
            assert res.status_code == 200
            tools = res.json()["tools"]
            assert len(tools) == 1
            assert tools[0]["name"] == "s7_read"
            assert tools[0]["server"] == "plc-mcp-bridge"
            assert tools[0]["category"] == "s7"

    def test_run_workflow_with_mock_engine(self, client):
        """mock 引擎后，执行工作流返回正确结果"""
        from orchestrator.core import WorkflowResult, StepResult

        mock_result = WorkflowResult(
            workflow_name="test_wf",
            ok=True,
            steps=[
                StepResult(tool="server.tool_a", ok=True, data={"v": 1}, duration_ms=5.0),
            ],
            total_duration_ms=10.0,
        )
        mock_engine = MagicMock()
        mock_engine.list_workflows.return_value = ["test_wf"]
        mock_engine.run_async = AsyncMock(return_value=mock_result)

        with patch("routes.orchestrator.get_engine", return_value=mock_engine):
            res = client.post(
                "/api/orchestrator/workflows/test_wf/run",
                json={"input": {"key": "val"}},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["ok"] is True
            assert data["workflow_name"] == "test_wf"
            assert len(data["steps"]) == 1
            assert data["steps"][0]["tool"] == "server.tool_a"

    def test_list_servers_with_mock_data(self, client):
        """mock 服务器列表后，servers 端点返回正确信息"""
        from orchestrator.registry import ServerInfo

        mock_server = ServerInfo(
            name="plc-mcp-bridge",
            description="S7 协议桥",
        )
        mock_server.tools = [MagicMock(), MagicMock()]
        mock_registry = MagicMock()
        mock_registry.list_servers.return_value = ["plc-mcp-bridge"]
        mock_registry.get_server.return_value = mock_server

        with patch("routes.orchestrator.get_registry", return_value=mock_registry):
            res = client.get("/api/orchestrator/servers")
            assert res.status_code == 200
            servers = res.json()["servers"]
            assert len(servers) == 1
            assert servers[0]["name"] == "plc-mcp-bridge"
            assert servers[0]["tool_count"] == 2
