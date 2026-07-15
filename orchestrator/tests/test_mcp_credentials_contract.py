"""MCP 凭据只能由 adapter 在传输边界注入。"""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.client.stdio import get_default_environment
from mcp.types import CallToolResult

from orchestrator.mcp_client import McpClientAdapter
from orchestrator.registry import ServerInfo
from orchestrator.server_configs import (
    DESKTOP_MCP,
    MITSUBISHI_MCP,
    MODBUS_MCP,
    OPCUA_MCP,
    PLC_MCP_BRIDGE,
    ROBOT_MCP,
    TEST_ECHO,
    TIA_MCP,
)


def _connected_adapter(server: ServerInfo) -> tuple[McpClientAdapter, AsyncMock]:
    adapter = McpClientAdapter(server)
    session = AsyncMock()
    session.call_tool = AsyncMock(
        return_value=CallToolResult(
            content=[],
            structuredContent={"status": "ok"},
        )
    )
    adapter._session = session
    adapter._connected = True
    return adapter, session


def _called_arguments(session: AsyncMock) -> dict:
    return session.call_tool.await_args.kwargs["arguments"]


class _StreamContext:
    def __init__(self, enter_error: BaseException | None = None):
        self._enter_error = enter_error

    async def __aenter__(self):
        if self._enter_error is not None:
            raise self._enter_error
        return MagicMock(), MagicMock()

    async def __aexit__(self, *_args):
        return None


class _SessionContext:
    def __init__(self, session: AsyncMock):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *_args):
        return None


class _CancelledExitContext:
    async def __aexit__(self, *_args):
        raise asyncio.CancelledError


class _TrackingExitContext:
    def __init__(self):
        self.exited = False

    async def __aexit__(self, *_args):
        self.exited = True


class _BlockingExitContext:
    def __init__(self, entered: asyncio.Event, release: asyncio.Event):
        self._entered = entered
        self._release = release
        self.exited = False

    async def __aexit__(self, *_args):
        self._entered.set()
        await self._release.wait()
        self.exited = True


class _FailingExitContext:
    def __init__(self, exception: Exception):
        self._exception = exception

    async def __aexit__(self, *_args):
        raise self._exception


class _StateProbeExitContext:
    def __init__(self, adapter: McpClientAdapter):
        self._adapter = adapter
        self.observed_state = None

    async def __aexit__(self, *_args):
        self.observed_state = (
            self._adapter._connected,
            self._adapter._credential,
        )


async def _connect_without_subprocess(
    adapter: McpClientAdapter,
    session: AsyncMock,
    captured: dict,
) -> None:
    def fake_stdio_client(params):
        captured["params"] = params
        return _StreamContext()

    with patch("orchestrator.mcp_client.stdio_client", side_effect=fake_stdio_client), patch(
        "orchestrator.mcp_client.ClientSession",
        return_value=_SessionContext(session),
    ):
        await adapter.connect()


def test_server_info_credential_metadata_defaults_are_secret_free():
    server = ServerInfo(name="test-mcp")

    assert server.credential_envs == ()
    assert server.credential_argument == "auth_token"


@pytest.mark.asyncio
async def test_adapter_injects_credential_without_mutating_caller_arguments(
    monkeypatch,
    caplog,
):
    internal_token = "  internal-secret  "
    monkeypatch.setenv("TEST_MCP_AUTH_TOKEN", internal_token)
    server = ServerInfo(
        name="test-mcp",
        credential_envs=("TEST_MCP_AUTH_TOKEN",),
    )
    adapter, session = _connected_adapter(server)
    adapter._credential = internal_token
    caller_arguments = {"description": "电机启停"}

    with caplog.at_level(logging.DEBUG, logger="orchestrator.mcp_client"):
        result = await adapter.call_tool("create_ladder_block", caller_arguments)

    assert result.ok is True
    assert caller_arguments == {"description": "电机启停"}
    assert _called_arguments(session) == {
        "description": "电机启停",
        "auth_token": internal_token,
    }
    assert _called_arguments(session) is not caller_arguments
    assert internal_token not in caplog.text


@pytest.mark.asyncio
async def test_tia_primary_credential_precedes_fallback(monkeypatch):
    monkeypatch.setenv("TIA_MCP_AUTH_TOKEN", "tia-primary")
    monkeypatch.setenv("MCP_AUTH_TOKEN", "shared-fallback")
    adapter, session = _connected_adapter(TIA_MCP)
    adapter._credential = "tia-primary"

    result = await adapter.call_tool("compile_project", {"project": "demo"})

    assert result.ok is True
    assert _called_arguments(session)["auth_token"] == "tia-primary"


@pytest.mark.asyncio
async def test_tia_uses_fallback_when_primary_is_missing(monkeypatch):
    monkeypatch.delenv("TIA_MCP_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("MCP_AUTH_TOKEN", "shared-fallback")
    adapter, session = _connected_adapter(TIA_MCP)
    adapter._credential = "shared-fallback"

    result = await adapter.call_tool("compile_project", {})

    assert result.ok is True
    assert _called_arguments(session)["auth_token"] == "shared-fallback"


@pytest.mark.asyncio
async def test_adapter_skips_empty_primary_credential(monkeypatch):
    monkeypatch.setenv("TIA_MCP_AUTH_TOKEN", "")
    monkeypatch.setenv("MCP_AUTH_TOKEN", "shared-fallback")
    adapter, session = _connected_adapter(TIA_MCP)
    adapter._credential = "shared-fallback"

    result = await adapter.call_tool("compile_project", {})

    assert result.ok is True
    assert _called_arguments(session)["auth_token"] == "shared-fallback"


@pytest.mark.asyncio
async def test_adapter_rejects_caller_credential_without_logging_it(
    monkeypatch,
    caplog,
):
    caller_token = "caller-controlled-secret"
    monkeypatch.setenv("TIA_MCP_AUTH_TOKEN", "internal-secret")
    adapter, session = _connected_adapter(TIA_MCP)
    caller_arguments = {"project": "demo", "auth_token": caller_token}

    with caplog.at_level(logging.DEBUG, logger="orchestrator.mcp_client"):
        result = await adapter.call_tool("compile_project", caller_arguments)

    assert result.ok is False
    assert result.kind == "credential_override"
    assert caller_arguments == {"project": "demo", "auth_token": caller_token}
    session.call_tool.assert_not_awaited()
    assert caller_token not in caplog.text


@pytest.mark.asyncio
async def test_adapter_fails_closed_when_all_credentials_are_missing(monkeypatch):
    monkeypatch.delenv("TIA_MCP_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("MCP_AUTH_TOKEN", "")
    adapter, session = _connected_adapter(TIA_MCP)

    result = await adapter.call_tool("compile_project", {"project": "demo"})

    assert result.ok is False
    assert result.kind == "credential_missing"
    session.call_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_connected_adapter_without_snapshot_does_not_reread_environment(
    monkeypatch,
):
    monkeypatch.setenv("TIA_MCP_AUTH_TOKEN", "new-token-after-connect")
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    adapter, session = _connected_adapter(TIA_MCP)
    adapter._credential = None

    result = await adapter.call_tool("compile_project", {})

    assert result.ok is False
    assert result.kind == "credential_missing"
    session.call_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_credential_call_exception_does_not_expose_token(caplog):
    token = "call-exception-internal-secret"
    adapter, session = _connected_adapter(TIA_MCP)
    adapter._credential = token
    session.call_tool.side_effect = RuntimeError(f"transport failed: {token}")

    with caplog.at_level(logging.DEBUG, logger="orchestrator.mcp_client"):
        result = await adapter.call_tool("compile_project", {})

    assert result.ok is False
    assert result.kind == "transport_error"
    assert "RuntimeError" in result.error
    assert token not in result.error
    assert token not in caplog.text
    session.call_tool.assert_awaited_once()


@pytest.mark.asyncio
async def test_server_without_credential_configuration_preserves_arguments():
    adapter, session = _connected_adapter(PLC_MCP_BRIDGE)
    caller_arguments = {"tag": "M0.0"}

    result = await adapter.call_tool("read_tag", caller_arguments)

    assert result.ok is True
    assert caller_arguments == {"tag": "M0.0"}
    assert _called_arguments(session) == caller_arguments
    assert _called_arguments(session) is not caller_arguments


@pytest.mark.asyncio
async def test_legacy_server_without_credential_metadata_calls_session_normally():
    server = SimpleNamespace(name="legacy-mcp")
    adapter, session = _connected_adapter(server)

    result = await adapter.call_tool("ping", {"value": 1})

    assert result.ok is True
    session.call_tool.assert_awaited_once_with(
        name="ping",
        arguments={"value": 1},
    )


@pytest.mark.asyncio
async def test_connect_passes_safe_defaults_and_all_declared_credentials(
    monkeypatch,
    caplog,
):
    primary_token = "stdio-primary-secret"
    fallback_token = "stdio-fallback-secret"
    monkeypatch.setenv("PATH", "contract-path")
    monkeypatch.setenv("APPDATA", "contract-appdata")
    monkeypatch.setenv("TIA_MCP_AUTH_TOKEN", primary_token)
    monkeypatch.setenv("MCP_AUTH_TOKEN", fallback_token)
    expected_env = get_default_environment()
    expected_env.update(
        {
            "TIA_MCP_AUTH_TOKEN": primary_token,
            "MCP_AUTH_TOKEN": fallback_token,
        }
    )
    adapter = McpClientAdapter(TIA_MCP)
    session = AsyncMock()
    session.initialize = AsyncMock()
    session.call_tool = AsyncMock(
        return_value=CallToolResult(content=[], structuredContent={"status": "ok"})
    )
    captured = {}

    with caplog.at_level(logging.DEBUG, logger="orchestrator.mcp_client"):
        await _connect_without_subprocess(adapter, session, captured)

    params = captured["params"]
    assert params.env == expected_env
    assert primary_token not in params.args
    assert fallback_token not in params.args
    assert primary_token not in caplog.text
    assert fallback_token not in caplog.text

    monkeypatch.setenv("TIA_MCP_AUTH_TOKEN", "changed-after-connect")
    result = await adapter.call_tool("compile_project", {"project": "demo"})

    assert result.ok is True
    assert _called_arguments(session)["auth_token"] == primary_token

    await adapter.disconnect()
    assert adapter._credential is None


@pytest.mark.asyncio
async def test_connect_omits_empty_primary_and_snapshots_fallback(monkeypatch):
    fallback_token = "stdio-shared-secret"
    monkeypatch.setenv("TIA_MCP_AUTH_TOKEN", "")
    monkeypatch.setenv("MCP_AUTH_TOKEN", fallback_token)
    expected_env = get_default_environment()
    expected_env["MCP_AUTH_TOKEN"] = fallback_token
    adapter = McpClientAdapter(TIA_MCP)
    session = AsyncMock()
    session.initialize = AsyncMock()
    session.call_tool = AsyncMock(
        return_value=CallToolResult(content=[], structuredContent={"status": "ok"})
    )
    captured = {}

    await _connect_without_subprocess(adapter, session, captured)

    assert captured["params"].env == expected_env
    assert "TIA_MCP_AUTH_TOKEN" not in captured["params"].env

    monkeypatch.setenv("MCP_AUTH_TOKEN", "changed-after-connect")
    await adapter.call_tool("compile_project", {})

    assert _called_arguments(session)["auth_token"] == fallback_token


@pytest.mark.asyncio
async def test_connect_fails_before_stdio_when_credentials_are_missing(monkeypatch):
    monkeypatch.delenv("TIA_MCP_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("MCP_AUTH_TOKEN", "")
    adapter = McpClientAdapter(TIA_MCP)
    session = AsyncMock()
    stdio_mock = MagicMock(return_value=_StreamContext())

    with patch("orchestrator.mcp_client.stdio_client", stdio_mock), patch(
        "orchestrator.mcp_client.ClientSession",
        return_value=_SessionContext(session),
    ):
        with pytest.raises(RuntimeError, match="缺少启动凭据"):
            await adapter.connect()

    stdio_mock.assert_not_called()


@pytest.mark.asyncio
async def test_connect_without_credential_configuration_keeps_sdk_default_behavior():
    adapter = McpClientAdapter(PLC_MCP_BRIDGE)
    session = AsyncMock()
    session.initialize = AsyncMock()
    captured = {}

    await _connect_without_subprocess(adapter, session, captured)

    assert captured["params"].env is None


@pytest.mark.asyncio
async def test_connect_failure_clears_credential_snapshot(monkeypatch):
    monkeypatch.setenv("TIA_MCP_AUTH_TOKEN", "temporary-secret")
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    adapter = McpClientAdapter(TIA_MCP)
    stream_context = _StreamContext(RuntimeError("连接失败"))

    with patch(
        "orchestrator.mcp_client.stdio_client",
        return_value=stream_context,
    ):
        with pytest.raises(RuntimeError, match="连接失败"):
            await adapter.connect()

    assert adapter._credential is None


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_point", ["environment", "stdio", "initialize"])
async def test_credential_connect_exception_does_not_expose_token(
    monkeypatch,
    caplog,
    failure_point,
):
    token = "connect-exception-internal-secret"
    monkeypatch.setenv("TIA_MCP_AUTH_TOKEN", token)
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    adapter = McpClientAdapter(TIA_MCP)
    session = AsyncMock()
    session.initialize = AsyncMock()
    environment = MagicMock(return_value=get_default_environment())
    stream_context = _StreamContext()
    if failure_point == "environment":
        environment.side_effect = RuntimeError(f"environment failed: {token}")
    elif failure_point == "stdio":
        stream_context = _StreamContext(RuntimeError(f"stdio failed: {token}"))
    else:
        session.initialize.side_effect = RuntimeError(f"initialize failed: {token}")

    with patch(
        "orchestrator.mcp_client.stdio_client",
        return_value=stream_context,
    ), patch(
        "orchestrator.mcp_client.ClientSession",
        return_value=_SessionContext(session),
    ), patch(
        "orchestrator.mcp_client.get_default_environment",
        environment,
    ), caplog.at_level(logging.DEBUG, logger="orchestrator.mcp_client"):
        with pytest.raises(RuntimeError) as caught:
            await adapter.connect()

    assert "RuntimeError" in str(caught.value)
    assert token not in str(caught.value)
    assert token not in caplog.text


@pytest.mark.asyncio
async def test_connect_cancellation_clears_credential_snapshot(monkeypatch):
    monkeypatch.setenv("TIA_MCP_AUTH_TOKEN", "temporary-secret")
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    adapter = McpClientAdapter(TIA_MCP)
    stream_context = _StreamContext(asyncio.CancelledError())

    with patch(
        "orchestrator.mcp_client.stdio_client",
        return_value=stream_context,
    ):
        with pytest.raises(asyncio.CancelledError):
            await adapter.connect()

    assert adapter._credential is None
    assert adapter._stdio_context is None
    assert adapter._session_context is None
    assert adapter._connected is False


@pytest.mark.asyncio
async def test_credential_disconnect_errors_do_not_log_token(caplog):
    token = "disconnect-exception-internal-secret"
    adapter = McpClientAdapter(TIA_MCP)
    adapter._connected = True
    adapter._credential = token
    adapter._session_context = _FailingExitContext(
        RuntimeError(f"session close failed: {token}")
    )
    adapter._stdio_context = _FailingExitContext(
        RuntimeError(f"stdio close failed: {token}")
    )

    with caplog.at_level(logging.WARNING, logger="orchestrator.mcp_client"):
        await adapter.disconnect()

    assert token not in caplog.text
    assert "session: RuntimeError" in caplog.text
    assert "stdio: RuntimeError" in caplog.text


@pytest.mark.asyncio
async def test_disconnect_closes_access_before_first_await():
    adapter = McpClientAdapter(TIA_MCP)
    adapter._connected = True
    adapter._credential = "snapshot-secret"
    probe = _StateProbeExitContext(adapter)
    adapter._session_context = probe

    await adapter.disconnect()

    assert probe.observed_state == (False, None)


@pytest.mark.asyncio
async def test_disconnect_cancellation_clears_credential_snapshot():
    adapter = McpClientAdapter(TIA_MCP)
    adapter._connected = True
    adapter._credential = "temporary-secret"
    adapter._session_context = _CancelledExitContext()
    stdio_context = _TrackingExitContext()
    adapter._stdio_context = stdio_context
    adapter._session = AsyncMock()
    adapter._read_stream = MagicMock()
    adapter._write_stream = MagicMock()

    with pytest.raises(asyncio.CancelledError):
        await adapter.disconnect()

    assert adapter._credential is None
    assert stdio_context.exited is True
    assert adapter._session_context is None
    assert adapter._stdio_context is None
    assert adapter._session is None
    assert adapter._read_stream is None
    assert adapter._write_stream is None
    assert adapter._connected is False


@pytest.mark.asyncio
async def test_connect_waits_for_in_progress_disconnect(monkeypatch):
    monkeypatch.setenv("TIA_MCP_AUTH_TOKEN", "new-connection-secret")
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    adapter = McpClientAdapter(TIA_MCP)
    adapter._connected = True
    adapter._credential = "old-connection-secret"
    adapter._session = AsyncMock(name="old_session")
    adapter._read_stream = MagicMock(name="old_read_stream")
    adapter._write_stream = MagicMock(name="old_write_stream")

    old_exit_entered = asyncio.Event()
    release_old_exit = asyncio.Event()
    old_session_context = _BlockingExitContext(
        old_exit_entered,
        release_old_exit,
    )
    old_stdio_context = _TrackingExitContext()
    adapter._session_context = old_session_context
    adapter._stdio_context = old_stdio_context

    new_session = AsyncMock(name="new_session")
    new_session.initialize = AsyncMock()
    new_stdio_context = _StreamContext()
    new_session_context = _SessionContext(new_session)
    stdio_mock = MagicMock(return_value=new_stdio_context)

    disconnect_task = asyncio.create_task(adapter.disconnect())
    connect_task = None
    observations = {}
    results = []
    try:
        await asyncio.wait_for(old_exit_entered.wait(), timeout=1)
        with patch(
            "orchestrator.mcp_client.stdio_client",
            stdio_mock,
        ), patch(
            "orchestrator.mcp_client.ClientSession",
            return_value=new_session_context,
        ):
            connect_task = asyncio.create_task(adapter.connect())
            await asyncio.sleep(0)
            observations = {
                "connect_completed_before_release": connect_task.done(),
                "new_stdio_started_before_release": stdio_mock.called,
            }
            release_old_exit.set()
            results = await asyncio.gather(
                disconnect_task,
                connect_task,
                return_exceptions=True,
            )
    finally:
        release_old_exit.set()
        pending = [
            task
            for task in (disconnect_task, connect_task)
            if task is not None and not task.done()
        ]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    assert results == [None, None]
    assert {
        **observations,
        "old_session_context_exited": old_session_context.exited,
        "old_stdio_context_exited": old_stdio_context.exited,
        "adapter_connected": adapter._connected,
        "adapter_session_is_new": adapter._session is new_session,
        "adapter_stdio_context_is_new": adapter._stdio_context is new_stdio_context,
        "adapter_session_context_is_new": (
            adapter._session_context is new_session_context
        ),
    } == {
        "connect_completed_before_release": False,
        "new_stdio_started_before_release": False,
        "old_session_context_exited": True,
        "old_stdio_context_exited": True,
        "adapter_connected": True,
        "adapter_session_is_new": True,
        "adapter_stdio_context_is_new": True,
        "adapter_session_context_is_new": True,
    }


def test_server_configs_declare_exact_credential_environment_priority():
    assert {
        server.name: server.credential_envs
        for server in (
            PLC_MCP_BRIDGE,
            TIA_MCP,
            OPCUA_MCP,
            MODBUS_MCP,
            MITSUBISHI_MCP,
            ROBOT_MCP,
            DESKTOP_MCP,
            TEST_ECHO,
        )
    } == {
        "plc-mcp-bridge": (),
        "tia-mcp": ("TIA_MCP_AUTH_TOKEN", "MCP_AUTH_TOKEN"),
        "opcua-mcp": ("MCP_AUTH_TOKEN",),
        "modbus-mcp": ("MCP_AUTH_TOKEN",),
        "mitsubishi-mcp": ("MCP_AUTH_TOKEN",),
        "robot-mcp": ("MCP_AUTH_TOKEN",),
        "desktop-mcp": (),
        "test-echo": (),
    }
