from pathlib import Path
import importlib.util
import importlib
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest


PROJECT_ROOT = Path(__file__).parent.parent


def _load_server(module_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(module_name, PROJECT_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _confirmation_api():
    try:
        from safety.confirmation import ConfirmationError, ConfirmationService
    except ModuleNotFoundError:
        return None, None
    return ConfirmationError, ConfirmationService


def test_confirmation_token_binds_write_and_can_only_be_consumed_once(tmp_path: Path):
    ConfirmationError, ConfirmationService = _confirmation_api()
    assert ConfirmationService is not None, "缺少一次性确认令牌服务"
    service = ConfirmationService(
        secret="test-confirmation-secret",
        store_path=tmp_path / "confirmations.sqlite3",
    )
    token = service.issue(
        operator="ai-agent",
        approver="local-human",
        target="DB1.MOTOR_RUN",
        value=1,
        device_id="s7:plcsim:factoryio",
        audit_id="audit-123",
        ttl_seconds=60,
    )

    claims = service.consume(
        token,
        operator="ai-agent",
        target="DB1.MOTOR_RUN",
        value=1,
        device_id="s7:plcsim:factoryio",
    )

    assert claims["audit_id"] == "audit-123"
    with pytest.raises(ConfirmationError, match="已使用"):
        service.consume(
            token,
            operator="ai-agent",
            target="DB1.MOTOR_RUN",
            value=1,
            device_id="s7:plcsim:factoryio",
        )


def test_confirmation_token_rejects_wrong_target_operator_and_expiry(tmp_path: Path):
    ConfirmationError, ConfirmationService = _confirmation_api()
    assert ConfirmationService is not None, "缺少一次性确认令牌服务"
    service = ConfirmationService(
        secret="test-confirmation-secret",
        store_path=tmp_path / "confirmations.sqlite3",
    )
    token = service.issue(
        operator="ai-agent",
        approver="local-human",
        target="DB1.MOTOR_RUN",
        value=1,
        device_id="s7:plcsim:factoryio",
        audit_id="audit-123",
        ttl_seconds=60,
    )

    with pytest.raises(ConfirmationError, match="目标"):
        service.consume(
            token,
            operator="ai-agent",
            target="DB1.OTHER",
            value=1,
            device_id="s7:plcsim:factoryio",
        )
    with pytest.raises(ConfirmationError, match="操作者"):
        service.consume(
            token,
            operator="other-agent",
            target="DB1.MOTOR_RUN",
            value=1,
            device_id="s7:plcsim:factoryio",
        )

    expired = service.issue(
        operator="ai-agent",
        approver="local-human",
        target="DB1.MOTOR_RUN",
        value=1,
        device_id="s7:plcsim:factoryio",
        audit_id="audit-456",
        ttl_seconds=-1,
    )
    with pytest.raises(ConfirmationError, match="过期"):
        service.consume(
            expired,
            operator="ai-agent",
            target="DB1.MOTOR_RUN",
            value=1,
            device_id="s7:plcsim:factoryio",
        )


@pytest.mark.asyncio
async def test_modbus_write_accepts_an_exact_confirmation_token_once(tmp_path: Path, monkeypatch):
    ConfirmationError, ConfirmationService = _confirmation_api()
    module = _load_server("modbus_confirmation_token_server", "mcp-servers/modbus-mcp/server.py")
    service = ConfirmationService(
        secret="test-confirmation-secret",
        store_path=tmp_path / "confirmations.sqlite3",
    )
    client = MagicMock()
    client.write_coil.return_value = MagicMock(isError=lambda: False)

    monkeypatch.setattr(module, "_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(module, "settings", types.SimpleNamespace(modbus_host="test-host", modbus_port=502))
    monkeypatch.setattr(module, "confirmation_service", service, raising=False)
    monkeypatch.setattr(module, "safety_validator", MagicMock(
        validate=MagicMock(return_value=MagicMock(allowed=True, needs_confirmation=True, reason="确认")),
    ))
    monkeypatch.setattr(module, "shadow_sim", MagicMock(simulate_write=AsyncMock(return_value=MagicMock(safe=True))))
    monkeypatch.setattr(module, "get_client", MagicMock(return_value=client))
    monkeypatch.setattr(module, "audit", MagicMock())

    from mcp_common.audit import authenticated_actor
    writer_actor = authenticated_actor("test-token", "modbus")
    token = service.issue(
        operator=writer_actor,
        approver="local-human",
        target="coil.1",
        value=True,
        device_id="modbus:test-host:502:unit-1",
        audit_id="audit-123",
    )
    first = await module.write_coil(1, True, auth_token="test-token", confirmation_token=token)
    assert first["status"] == "ok"
    assert client.write_coil.call_count == 1

    second = await module.write_coil(1, True, auth_token="test-token", confirmation_token=token)
    assert second["status"] == "blocked"
    assert "已使用" in second["reason"]
    assert client.write_coil.call_count == 1


@pytest.mark.asyncio
async def test_modbus_register_rejects_a_token_for_a_different_target(tmp_path: Path, monkeypatch):
    _, ConfirmationService = _confirmation_api()
    module = _load_server("modbus_register_confirmation_token_server", "mcp-servers/modbus-mcp/server.py")
    service = ConfirmationService(secret="test-confirmation-secret", store_path=tmp_path / "confirmations.sqlite3")
    client = MagicMock()
    client.write_register.return_value = MagicMock(isError=lambda: False)

    monkeypatch.setattr(module, "_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(module, "settings", types.SimpleNamespace(modbus_host="test-host", modbus_port=502))
    monkeypatch.setattr(module, "confirmation_service", service, raising=False)
    monkeypatch.setattr(module, "safety_validator", MagicMock(
        validate=MagicMock(return_value=MagicMock(allowed=True, needs_confirmation=True, reason="确认")),
    ))
    monkeypatch.setattr(module, "shadow_sim", MagicMock(simulate_write=AsyncMock(return_value=MagicMock(safe=True))))
    monkeypatch.setattr(module, "get_client", MagicMock(return_value=client))
    monkeypatch.setattr(module, "audit", MagicMock())
    from mcp_common.audit import authenticated_actor
    token = service.issue(
        operator=authenticated_actor("test-token", "modbus"),
        approver="local-human", target="register.2", value=8,
        device_id="modbus:test-host:502:unit-1", audit_id="audit-123",
    )

    result = await module.write_register(1, 8, auth_token="test-token", confirmation_token=token)

    assert result["status"] == "blocked"
    assert "目标" in result["reason"]
    client.write_register.assert_not_called()


@pytest.mark.asyncio
async def test_mitsubishi_write_accepts_an_exact_confirmation_token_once(tmp_path: Path, monkeypatch):
    _, ConfirmationService = _confirmation_api()
    module = _load_server("mitsubishi_confirmation_token_server", "mcp-servers/mitsubishi-mcp/server.py")
    service = ConfirmationService(secret="test-confirmation-secret", store_path=tmp_path / "confirmations.sqlite3")
    reader = MagicMock()
    reader.read = AsyncMock(return_value=b"ok")
    writer = MagicMock()
    writer.drain = AsyncMock()

    monkeypatch.setattr(module, "_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(module, "settings", types.SimpleNamespace(melsec_host="test-host", melsec_port=5000))
    monkeypatch.setattr(module, "confirmation_service", service, raising=False)
    monkeypatch.setattr(module, "safety_validator", MagicMock(
        validate=MagicMock(return_value=MagicMock(allowed=True, needs_confirmation=True, reason="确认")),
    ))
    monkeypatch.setattr(module, "shadow_sim", MagicMock(simulate_write=AsyncMock(return_value=MagicMock(safe=True))))
    monkeypatch.setattr(module, "get_connection", AsyncMock(return_value=(reader, writer)))
    monkeypatch.setattr(module, "build_write_request", MagicMock(return_value=b"request"))
    monkeypatch.setattr(module, "parse_write_response", MagicMock())
    monkeypatch.setattr(module, "audit", MagicMock())
    from mcp_common.audit import authenticated_actor
    token = service.issue(
        operator=authenticated_actor("test-token", "melsec"),
        approver="local-human", target="M100", value=1,
        device_id="melsec:test-host:5000", audit_id="audit-123",
    )

    first = await module.write_device("M100", 1, auth_token="test-token", confirmation_token=token)
    assert first["status"] == "ok"
    assert writer.write.call_count == 1

    second = await module.write_device("M100", 1, auth_token="test-token", confirmation_token=token)
    assert second["status"] == "blocked"
    assert "已使用" in second["reason"]
    assert writer.write.call_count == 1


@pytest.mark.asyncio
async def test_opcua_write_accepts_an_exact_confirmation_token_once(tmp_path: Path, monkeypatch):
    _, ConfirmationService = _confirmation_api()
    module = _load_server("opcua_confirmation_token_server", "mcp-servers/opcua-mcp/server.py")
    service = ConfirmationService(secret="test-confirmation-secret", store_path=tmp_path / "confirmations.sqlite3")
    node = MagicMock()
    node.write_value = AsyncMock()
    node.read_value = AsyncMock(return_value=True)
    client = MagicMock()
    client.get_node.return_value = node

    monkeypatch.setattr(module, "_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(module, "_client", client)
    monkeypatch.setattr(module, "_endpoint", "opc.tcp://test-host:4840")
    monkeypatch.setattr(module, "confirmation_service", service, raising=False)
    monkeypatch.setattr(module, "safety_validator", MagicMock(
        validate=MagicMock(return_value=MagicMock(allowed=True, needs_confirmation=True, reason="确认")),
    ))
    monkeypatch.setattr(module, "shadow_sim", MagicMock(simulate_write=AsyncMock(return_value=MagicMock(safe=True))))
    monkeypatch.setattr(module, "safety", MagicMock(
        check_interlock=AsyncMock(return_value=(True, "ok")),
        check_value_range=MagicMock(return_value=(True, "ok")),
    ))
    monkeypatch.setattr(module, "_audit", MagicMock())
    from mcp_common.audit import authenticated_actor
    token = service.issue(
        operator=authenticated_actor("test-token", "opcua"),
        approver="local-human", target="ns=2;s=MOTOR_1", value="1",
        device_id="opcua:opc.tcp://test-host:4840", audit_id="audit-123",
    )

    first = await module.write_node(
        "ns=2;s=MOTOR_1", "1", data_type="bool", auth_token="test-token", confirmation_token=token,
    )
    assert "已写入" in first
    assert node.write_value.await_count == 1

    second = await module.write_node(
        "ns=2;s=MOTOR_1", "1", data_type="bool", auth_token="test-token", confirmation_token=token,
    )
    assert "已使用" in second
    assert node.write_value.await_count == 1


def test_s7_write_accepts_an_exact_confirmation_token_once(tmp_path: Path, monkeypatch):
    _, ConfirmationService = _confirmation_api()
    bridge_dir = PROJECT_ROOT / "mcp-servers" / "plc-mcp-bridge"
    if str(bridge_dir) not in sys.path:
        sys.path.insert(0, str(bridge_dir))
    module = importlib.import_module("tools_s7")
    service = ConfirmationService(secret="test-confirmation-secret", store_path=tmp_path / "confirmations.sqlite3")
    adapter = MagicMock()
    adapter.device_id = "s7:test-host:0:1"
    adapter.read_address.return_value = 0
    adapter.parse_write_value.return_value = True
    adapter.write_address.return_value = "写入成功"

    monkeypatch.setattr(module, "SAFETY_AVAILABLE", True)
    monkeypatch.setattr(module, "adapter", adapter)
    monkeypatch.setattr(module, "confirmation_service", service, raising=False)
    monkeypatch.setattr(module, "safety_val", MagicMock(
        resolve_s7_write_address=MagicMock(return_value={
            "target": "DB1.MOTOR_RUN", "type": "bool",
        }),
        validate=MagicMock(return_value=MagicMock(allowed=True, needs_confirmation=True, reason="确认")),
    ))
    monkeypatch.setattr(module, "shadow_sim", MagicMock(simulate_write=AsyncMock(return_value=MagicMock(safe=True))))
    monkeypatch.setattr(module, "_audit", MagicMock())
    token = service.issue(
        operator="ai-agent", approver="local-human", target="M0.1", value=True,
        device_id="s7:test-host:0:1", audit_id="audit-123",
    )

    first = __import__("asyncio").run(module.s7_write(
        "M0.1", "true", operator="ai-agent", confirmation_token=token,
    ))
    assert "写入成功" in first
    assert adapter.write_address.call_count == 1

    second = __import__("asyncio").run(module.s7_write(
        "M0.1", "true", operator="ai-agent", confirmation_token=token,
    ))
    assert "已使用" in second
    assert adapter.write_address.call_count == 1
