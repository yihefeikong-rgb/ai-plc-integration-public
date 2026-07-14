import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


PROJECT_ROOT = Path(__file__).parent.parent


def load_server(module_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(
        module_name,
        PROJECT_ROOT / relative_path,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def confirmation_result():
    return MagicMock(
        allowed=True,
        needs_confirmation=True,
        reason="需要人工确认",
    )


@pytest.mark.asyncio
async def test_modbus_confirmation_blocks_before_client_access(monkeypatch):
    module = load_server("modbus_confirmation_server", "mcp-servers/modbus-mcp/server.py")
    client_factory = MagicMock()

    monkeypatch.setattr(module, "_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(
        module,
        "safety_validator",
        MagicMock(validate=MagicMock(return_value=confirmation_result())),
    )
    monkeypatch.setattr(
        module,
        "shadow_sim",
        MagicMock(simulate_write=AsyncMock(return_value=MagicMock(safe=True))),
    )
    monkeypatch.setattr(module, "get_client", client_factory)
    monkeypatch.setattr(module, "audit", MagicMock())

    result = await module.write_coil(1, True, auth_token="test-token")

    assert result["status"] == "blocked"
    assert "人工确认" in result["reason"]
    client_factory.assert_not_called()


@pytest.mark.asyncio
async def test_mitsubishi_confirmation_blocks_before_connection(monkeypatch):
    module = load_server(
        "mitsubishi_confirmation_server",
        "mcp-servers/mitsubishi-mcp/server.py",
    )
    connection_factory = AsyncMock()

    monkeypatch.setattr(module, "_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(
        module,
        "safety_validator",
        MagicMock(validate=MagicMock(return_value=confirmation_result())),
    )
    monkeypatch.setattr(
        module,
        "shadow_sim",
        MagicMock(simulate_write=AsyncMock(return_value=MagicMock(safe=True))),
    )
    monkeypatch.setattr(module, "get_connection", connection_factory)
    monkeypatch.setattr(module, "audit", MagicMock())

    result = await module.write_device("M100", 1, auth_token="test-token")

    assert result["status"] == "blocked"
    assert "人工确认" in result["reason"]
    connection_factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_opcua_confirmation_blocks_before_node_write(monkeypatch):
    module = load_server("opcua_confirmation_server", "mcp-servers/opcua-mcp/server.py")
    node = MagicMock()
    node.write_value = AsyncMock()
    client = MagicMock()
    client.get_node.return_value = node

    monkeypatch.setattr(module, "_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(module, "_client", client)
    monkeypatch.setattr(
        module,
        "safety_validator",
        MagicMock(validate=MagicMock(return_value=confirmation_result())),
    )
    monkeypatch.setattr(
        module,
        "shadow_sim",
        MagicMock(simulate_write=AsyncMock(return_value=MagicMock(safe=True))),
    )
    monkeypatch.setattr(
        module,
        "safety",
        MagicMock(
            check_interlock=AsyncMock(return_value=(True, "ok")),
            check_value_range=MagicMock(return_value=(True, "ok")),
        ),
    )
    monkeypatch.setattr(module, "_audit", MagicMock())

    result = await module.write_node("ns=2;s=MOTOR_1", "1", auth_token="test-token")

    assert "人工确认" in result
    client.get_node.assert_not_called()
    node.write_value.assert_not_awaited()
