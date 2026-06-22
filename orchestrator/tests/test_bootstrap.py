"""
测试 TS006 — 编排层启动引导 (bootstrap)。

覆盖场景:
- 所有服务器连接成功
- 部分服务器失败
- 所有服务器失败
- 工作流自动注册
- shutdown 调用 pool.disconnect_all()
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from orchestrator.bootstrap import bootstrap, shutdown, BootstrapResult


@pytest.fixture
def fresh_engine():
    """每个测试用独立的引擎实例，避免全局单例状态污染"""
    from orchestrator.core import OrchestratorEngine

    return OrchestratorEngine()


def _make_server_list(names: list[str]) -> list:
    """构造 ServerInfo 列表（仅用于测试，不启动真实服务器）"""
    from orchestrator.registry import ServerInfo

    return [ServerInfo(name=n) for n in names]


def _mock_pool(
    connect_ok: set[str] | None = None,
    tools_map: dict[str, list] | None = None,
):
    """构造模拟连接池。

    Args:
        connect_ok: 连接成功的服务器名集合，未列出的会抛异常
        tools_map: 每个服务器返回的工具列表
    """
    pool = AsyncMock()
    connect_ok = connect_ok or set()
    tools_map = tools_map or {}

    async def _connect_side_effect(info):
        if info.name not in connect_ok:
            raise ConnectionError(f"无法连接 {info.name}")

    pool.connect_server = AsyncMock(side_effect=_connect_side_effect)

    def _get_adapter_side_effect(name):
        if name not in connect_ok:
            return None
        adapter = AsyncMock()
        tools = tools_map.get(name, [])
        adapter.list_tools = AsyncMock(return_value=tools)
        return adapter

    pool.get_adapter = MagicMock(side_effect=_get_adapter_side_effect)
    pool.disconnect_all = AsyncMock()

    return pool


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bootstrap_all_success(fresh_engine):
    """所有服务器连接成功 → connected 包含所有名称"""
    from orchestrator.registry import ToolInfo

    server_list = _make_server_list(["srv-a", "srv-b", "srv-c"])
    tools_map = {
        "srv-a": [ToolInfo(name="tool_a1")],
        "srv-b": [ToolInfo(name="tool_b1"), ToolInfo(name="tool_b2")],
        "srv-c": [ToolInfo(name="tool_c1")],
    }
    pool = _mock_pool(connect_ok={"srv-a", "srv-b", "srv-c"}, tools_map=tools_map)

    result = await bootstrap(
        pool=pool, engine=fresh_engine, server_list=server_list
    )

    assert sorted(result.connected) == ["srv-a", "srv-b", "srv-c"]
    assert result.failed == []


@pytest.mark.asyncio
async def test_bootstrap_partial_failure(fresh_engine):
    """部分服务器失败 → 成功的在 connected，失败的在 failed"""
    server_list = _make_server_list(["good", "bad", "good2"])
    pool = _mock_pool(connect_ok={"good", "good2"})

    result = await bootstrap(
        pool=pool, engine=fresh_engine, server_list=server_list
    )

    assert sorted(result.connected) == ["good", "good2"]
    assert len(result.failed) == 1
    assert result.failed[0][0] == "bad"
    assert "bad" in result.failed[0][1]


@pytest.mark.asyncio
async def test_bootstrap_all_failure(fresh_engine):
    """所有服务器失败 → connected 为空，failed 包含所有"""
    server_list = _make_server_list(["x", "y"])
    pool = _mock_pool(connect_ok=set())

    result = await bootstrap(
        pool=pool, engine=fresh_engine, server_list=server_list
    )

    assert result.connected == []
    assert len(result.failed) == 2
    failed_names = {name for name, _ in result.failed}
    assert failed_names == {"x", "y"}


@pytest.mark.asyncio
async def test_bootstrap_registers_workflows(fresh_engine):
    """工作流自动注册 → engine.list_workflows() 包含 'tia_download'"""
    pool = _mock_pool(connect_ok=set())

    await bootstrap(pool=pool, engine=fresh_engine, server_list=[])

    assert "tia_download" in fresh_engine.list_workflows()


@pytest.mark.asyncio
async def test_shutdown_calls_disconnect_all():
    """shutdown 调用 pool.disconnect_all()"""
    pool = AsyncMock()
    pool.disconnect_all = AsyncMock()

    await shutdown(pool=pool)

    pool.disconnect_all.assert_awaited_once()
