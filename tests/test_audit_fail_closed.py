"""生产控制动作的审计 fail-closed 行为。"""

import json
import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from mcp_common.audit import AuditConfigurationError, AuditLogger, AuditStorageError


def _load_module(module_name: str, relative_path: str):
    root = Path(__file__).parent.parent
    spec = importlib.util.spec_from_file_location(module_name, root / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_production_rejects_missing_hmac_key(tmp_path, monkeypatch):
    monkeypatch.delenv("AUDIT_HMAC_KEY", raising=False)

    with pytest.raises(AuditConfigurationError, match="AUDIT_HMAC_KEY"):
        AuditLogger(tmp_path / "audit.log", production=True)


def test_production_rejects_missing_authenticated_actor(tmp_path):
    logger = AuditLogger(tmp_path / "audit.log", hmac_key="test-key", production=True)

    with pytest.raises(AuditConfigurationError, match="已认证操作者"):
        logger.ensure_control_ready("")


def test_production_rejects_unwritable_audit_storage(tmp_path, monkeypatch):
    logger = AuditLogger(tmp_path / "audit.log", hmac_key="test-key", production=True)

    def unavailable():
        raise OSError("storage unavailable")

    monkeypatch.setattr(logger, "_ensure_storage_writable", unavailable)
    with pytest.raises(AuditStorageError, match="storage unavailable"):
        logger.ensure_control_ready("local-session:abc")


def test_audit_redacts_secrets_before_persisting(tmp_path):
    log_path = tmp_path / "audit.log"
    logger = AuditLogger(log_path, hmac_key="test-key")
    logger.log_operation(
        "control_intent",
        actor="local-session:abc",
        params={"api_key": "do-not-store", "nested": {"token": "secret"}},
        detail="authorization=Bearer-do-not-store",
        safe="kept",
    )

    entry = json.loads(log_path.read_text(encoding="utf-8"))
    serialized = json.dumps(entry, ensure_ascii=False)
    assert "do-not-store" not in serialized
    assert "secret" not in serialized
    assert entry["safe"] == "kept"


@pytest.mark.asyncio
async def test_orchestrator_blocks_control_before_call_when_audit_is_unavailable(monkeypatch):
    """审计前置检查失败时，变更工具不得抵达 MCP 连接池。"""
    from orchestrator.core import WorkflowContext

    class UnavailableAudit:
        def begin_control_operation(self, *args, **kwargs):
            raise AuditStorageError("audit storage unavailable")

    pool = type("Pool", (), {"call_tool": AsyncMock()})()
    monkeypatch.setattr("mcp_common.audit.get_audit_logger", lambda: UnavailableAudit())
    context = WorkflowContext(
        input={"authenticated_operator": "local-session:abc"},
        _pool=pool,
    )

    with pytest.raises(AuditStorageError, match="audit storage unavailable"):
        await context.call_async("tia-mcp.download_project", project_path="demo.ap21")
    pool.call_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_direct_modbus_write_is_blocked_before_client_when_audit_is_unavailable(monkeypatch):
    """直接 MCP 调用也必须在网络写入前通过审计闸门。"""
    module = _load_module("modbus_audit_gate_server", "mcp-servers/modbus-mcp/server.py")
    client_factory = MagicMock()
    audit = MagicMock()
    audit.begin_control_operation.side_effect = AuditStorageError("audit storage unavailable")

    monkeypatch.setattr(module, "_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(module, "safety_validator", MagicMock(
        validate=MagicMock(return_value=MagicMock(allowed=True, needs_confirmation=False)),
    ))
    monkeypatch.setattr(module, "shadow_sim", MagicMock(
        simulate_write=AsyncMock(return_value=MagicMock(safe=True)),
    ))
    monkeypatch.setattr(module, "audit", audit)
    monkeypatch.setattr(module, "get_client", client_factory)

    result = await module.write_coil(1, True, auth_token="test-token")
    assert result["status"] == "error"
    client_factory.assert_not_called()
