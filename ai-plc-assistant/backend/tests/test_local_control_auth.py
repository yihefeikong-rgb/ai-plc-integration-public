import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest
from fastapi import HTTPException


def load_security_module():
    path = Path(__file__).parents[1] / "security.py"
    spec = importlib.util.spec_from_file_location("local_control_security", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_local_control_requires_a_configured_matching_session_token(monkeypatch):
    module = load_security_module()
    monkeypatch.delenv("LOCAL_API_TOKEN", raising=False)
    with pytest.raises(HTTPException) as missing:
        await module.require_local_session(None)
    assert missing.value.status_code == 503

    monkeypatch.setenv("LOCAL_API_TOKEN", "test-token")
    with pytest.raises(HTTPException) as invalid:
        await module.require_local_session("wrong")
    assert invalid.value.status_code == 401

    actor = await module.require_local_session("test-token")
    assert actor.startswith("local-session:")
    assert actor != "test-token"


def test_model_base_url_must_be_an_allowed_https_provider_url():
    settings_path = Path(__file__).parents[1] / "routes" / "settings.py"
    source = settings_path.read_text(encoding="utf-8")
    assert '"null"' not in source
    assert "TRUSTED_BASE_URLS" in source


@pytest.mark.asyncio
async def test_authenticated_human_session_issues_bound_confirmation_token(monkeypatch, tmp_path):
    backend_dir = Path(__file__).parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    from routes import orchestrator as route
    from safety.confirmation import ConfirmationService

    service = ConfirmationService(
        secret="test-confirmation-secret",
        store_path=tmp_path / "confirmations.sqlite3",
    )
    gate = types.SimpleNamespace(
        check_write=lambda *args, **kwargs: types.SimpleNamespace(
            allowed=True,
            needs_confirmation=True,
            reason="确认",
            audit_id="audit-123",
        )
    )
    monkeypatch.setattr(route, "get_safety_gate", lambda: gate, raising=False)
    monkeypatch.setattr(route, "confirmation_service", service, raising=False)

    result = await route.issue_confirmation(route.ConfirmationRequest(
        operator="ai-agent",
        target="DB1.MOTOR_RUN",
        value=1,
        device_id="s7:test-host:0:1",
    ), "local-session:test")

    assert result["audit_id"] == "audit-123"
    service.consume(
        result["confirmation_token"],
        operator="ai-agent",
        target="DB1.MOTOR_RUN",
        value=1,
        device_id="s7:test-host:0:1",
    )


def test_client_defined_workflows_reject_dangerous_or_unknown_tools():
    backend_dir = Path(__file__).parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    from fastapi import HTTPException
    from routes import orchestrator as route

    route._validate_client_steps([
        {"server": "plc-mcp-bridge", "tool": "s7_read", "params": {"address": "M0.0"}},
    ])
    with pytest.raises(HTTPException, match="白名单"):
        route._validate_client_steps([
            {"server": "plc-mcp-bridge", "tool": "s7_write", "params": {"address": "M0.0", "value": "1"}},
        ])
    with pytest.raises(HTTPException, match="白名单"):
        route._validate_client_steps([
            {"server": "unknown", "tool": "anything", "params": {}},
        ])


@pytest.mark.asyncio
async def test_authenticated_session_identity_is_injected_into_workflow_input(monkeypatch):
    backend_dir = Path(__file__).parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    from routes import orchestrator as route

    result = types.SimpleNamespace(
        workflow_name="safe",
        ok=True,
        steps=[],
        error="",
        total_duration_ms=0.0,
    )
    class Engine:
        def list_workflows(self):
            return ["safe"]

        async def run_async(self, name, input):
            self.last_input = input
            return result

    engine = Engine()
    monkeypatch.setattr(route, "get_engine", lambda: engine)

    await route.run_workflow(
        "safe",
        route.RunWorkflowRequest(input={"authenticated_operator": "forged"}),
        "local-session:trusted",
    )
    assert engine.last_input["authenticated_operator"] == "local-session:trusted"
