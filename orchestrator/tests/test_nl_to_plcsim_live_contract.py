from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from orchestrator.bootstrap import bootstrap
from orchestrator.core import OrchestratorEngine
from orchestrator.mcp_client import ToolResult
from orchestrator.registry import Registry
from orchestrator.server_configs import ServerInfo
from orchestrator.workflows.nl_to_plcsim_pipeline import (
    register_nl_to_plcsim_pipeline_workflow,
)


class FakeAdapter:
    async def list_tools(self):
        return []


class FakePool:
    def __init__(self):
        self.connect_server = AsyncMock()
        self._adapter = FakeAdapter()

    def get_adapter(self, _name):
        return self._adapter


class FailingPool(FakePool):
    def __init__(self):
        super().__init__()
        del self.connect_server

    async def connect_server(self, _server):
        raise OSError("模拟 MCP 连接失败")

    async def disconnect_server(self, _name):
        return None


class AllowSafetyGate:
    def check_write(self, *_args, **_kwargs):
        return SimpleNamespace(allowed=True, needs_confirmation=False, reason="")


class ContractPool:
    """离线 MCP 适配器：只接受实际 MCP schema 支持的参数。"""

    expected_calls = [
        ("tia-mcp", "create_ladder_block", {"description": "电机启停", "block_name": "MotorControl"}),
        ("tia-mcp", "call_fb_in_ob1", {"fb_names": ["MotorControl"]}),
        ("plc-mcp-bridge", "plc_compile_project", {}),
        ("plc-mcp-bridge", "plc_download_project", {"method": "auto", "compile_first": False}),
        ("plc-mcp-bridge", "s7_connect", {}),
        ("plc-mcp-bridge", "s7_read", {"address": "M0.0"}),
        ("plc-mcp-bridge", "s7_disconnect", {}),
    ]

    def __init__(self):
        self.calls = []

    async def call_tool(self, server_name, tool_name, arguments):
        self.calls.append((server_name, tool_name, arguments))
        expected = self.expected_calls[len(self.calls) - 1]
        assert (server_name, tool_name, arguments) == expected
        if tool_name == "create_ladder_block":
            return ToolResult.success({"status": "ok", "blockName": "MotorControl"})
        return ToolResult.success({"status": "ok"})


@pytest.mark.asyncio
async def test_bootstrap_injects_the_connected_pool_and_safety_gate_into_engine():
    engine = OrchestratorEngine(registry=Registry())
    pool = FakePool()
    server = ServerInfo(name="test-server")

    result = await bootstrap(pool=pool, engine=engine, server_list=[server])

    assert engine._pool is pool
    assert engine._safety_gate is not None
    assert result.connected == ["test-server"]


@pytest.mark.asyncio
async def test_bootstrap_reports_connection_failure_without_losing_injected_engine_state():
    engine = OrchestratorEngine(registry=Registry())
    pool = FailingPool()
    server = ServerInfo(name="unreachable")

    result = await bootstrap(pool=pool, engine=engine, server_list=[server])

    assert engine._pool is pool
    assert engine._safety_gate is not None
    assert result.connected == []
    assert result.failed == [("unreachable", "模拟 MCP 连接失败")]


@pytest.mark.asyncio
async def test_nl_to_plcsim_uses_only_the_actual_mcp_tool_schemas():
    engine = OrchestratorEngine(registry=Registry())
    pool = ContractPool()
    engine.set_pool(pool)
    engine.set_safety_gate(AllowSafetyGate())
    register_nl_to_plcsim_pipeline_workflow(engine)

    result = await engine.run_async(
        "nl_to_plcsim_pipeline",
        input={"description": "电机启停", "block_name": "MotorControl"},
    )

    assert result.ok is True
    assert pool.calls == ContractPool.expected_calls


@pytest.mark.asyncio
async def test_nl_to_plcsim_rejects_target_overrides_before_calling_mcp():
    engine = OrchestratorEngine(registry=Registry())
    pool = ContractPool()
    engine.set_pool(pool)
    engine.set_safety_gate(AllowSafetyGate())
    register_nl_to_plcsim_pipeline_workflow(engine)

    result = await engine.run_async(
        "nl_to_plcsim_pipeline",
        input={"description": "电机启停", "plc_ip": "10.0.0.2"},
    )

    assert result.ok is False
    assert "不支持的工作流参数: plc_ip" in result.error
    assert pool.calls == []


@pytest.mark.asyncio
async def test_nl_to_plcsim_accepts_authenticated_actor_as_execution_metadata():
    engine = OrchestratorEngine(registry=Registry())
    pool = ContractPool()
    engine.set_pool(pool)
    engine.set_safety_gate(AllowSafetyGate())
    register_nl_to_plcsim_pipeline_workflow(engine)
    workflow_input = {
        "description": "电机启停",
        "block_name": "MotorControl",
        "authenticated_operator": "local-session:test-actor",
    }

    result = await engine.run_async(
        "nl_to_plcsim_pipeline",
        input=workflow_input,
    )

    assert result.ok is True, f"{result.error}; MCP calls: {pool.calls!r}"
    assert result.error == ""
    assert pool.calls == ContractPool.expected_calls
    assert workflow_input == {
        "description": "电机启停",
        "block_name": "MotorControl",
        "authenticated_operator": "local-session:test-actor",
    }
