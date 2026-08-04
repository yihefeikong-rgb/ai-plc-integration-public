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
    monkeypatch.setattr(module.app_config, "local_api_token", "")
    with pytest.raises(HTTPException) as missing:
        await module.require_local_session(None)
    assert missing.value.status_code == 503

    monkeypatch.setattr(module.app_config, "local_api_token", "test-token")
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
    # S7 写入方身份由共享认证令牌派生（与 tools_s7._authenticated_actor 一致）
    monkeypatch.setenv("MCP_AUTH_TOKEN", "test-shared-token")

    result = await route.issue_confirmation(route.ConfirmationRequest(
        operator="ai-agent",
        target="DB1.MOTOR_RUN",
        value=1,
        device_id="s7:test-host:0:1",
    ), "local-session:test")

    assert result["audit_id"] == "audit-123"
    # 消费端与签发端一致：用共享令牌派生 s7 写入方主体（不信任自报 operator）
    from mcp_common.audit import authenticated_actor
    consume_operator = authenticated_actor("test-shared-token", "s7")
    service.consume(
        result["confirmation_token"],
        operator=consume_operator,
        target="DB1.MOTOR_RUN",
        value=1,
        device_id="s7:test-host:0:1",
    )


@pytest.mark.asyncio
async def test_workflow_confirmation_issued_and_consumed(monkeypatch, tmp_path):
    """人工签发的工作流级确认令牌必须能被编排层真实消费（一次性、绑定工作流名）。"""
    backend_dir = Path(__file__).parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    from routes import orchestrator as route
    from safety.confirmation import ConfirmationService, ConfirmationError

    service = ConfirmationService(
        secret="test-confirmation-secret",
        store_path=tmp_path / "wf-confirmations.sqlite3",
    )
    monkeypatch.setattr(route, "confirmation_service", service, raising=False)

    # 人工签发工作流级确认令牌
    result = await route.issue_confirmation(route.ConfirmationRequest(
        operator="ai-agent",
        target="",
        value=None,
        device_id="",
        ttl_seconds=60,
        purpose="workflow",
        workflow_name="nl_to_plcsim_pipeline",
    ), "local-session:test")

    token = result["confirmation_token"]
    assert token

    # 编排层（同一 ConfirmationService 实例）真实消费：绑定工作流名
    service.consume(
        token,
        operator="wf:nl_to_plcsim_pipeline",
        target="_wf.nl_to_plcsim_pipeline",
        value="run",
        device_id="workflow",
    )

    # 一次性：再次消费必须失败
    with pytest.raises(ConfirmationError):
        service.consume(
            token,
            operator="wf:nl_to_plcsim_pipeline",
            target="_wf.nl_to_plcsim_pipeline",
            value="run",
            device_id="workflow",
        )


def test_confirmation_request_full_flow(tmp_path, monkeypatch):
    """人工审批全流程：AI 创建请求 → 人工批准签发令牌 → AI 一次性领取 → 消费。"""
    from safety.confirmation import ConfirmationService
    from safety.confirmation_requests import ConfirmationRequestStore

    store = ConfirmationRequestStore(
        path=tmp_path / "requests.json",
        service=ConfirmationService(
            secret="test-secret", store_path=tmp_path / "confirm.sqlite3"),
    )

    # 1) AI 创建审批请求
    record = store.create("nl_to_plcsim_pipeline", "下载电机程序", "ai-agent")
    request_id = record["request_id"]
    assert record["status"] == "pending"
    assert store.list()[0]["status"] == "pending"

    # 2) 人工批准 → 签发一次性工作流级令牌
    result = store.approve(request_id, "local-session:test")
    assert result["status"] == "approved"
    token = result["confirmation_token"]
    assert token

    # 3) AI 凭 request_id 一次性领取（重复领取失败）
    taken = store.take_token(request_id)
    assert taken == token
    assert store.take_token(request_id) is None

    # 4) 领取的令牌可被编排层真实消费（一次）
    store._service.consume(
        taken,
        operator="wf:nl_to_plcsim_pipeline",
        target="_wf.nl_to_plcsim_pipeline",
        value="run",
        device_id="workflow",
    )


def test_confirmation_request_deny(tmp_path):
    """人工拒绝后不能再批准。"""
    from safety.confirmation import ConfirmationService
    from safety.confirmation_requests import ConfirmationRequestStore

    store = ConfirmationRequestStore(
        path=tmp_path / "requests.json",
        service=ConfirmationService(
            secret="test-secret", store_path=tmp_path / "confirm.sqlite3"),
    )
    record = store.create("tia_multi_block_pipeline", "导入 3 个块", "ai-agent")
    result = store.deny(record["request_id"], "local-session:test")
    assert result["status"] == "denied"
    import pytest as _pytest
    with _pytest.raises(ValueError):
        store.approve(record["request_id"], "local-session:test")


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
