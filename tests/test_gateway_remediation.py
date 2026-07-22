"""PLC Gateway 第二轮整改的离线回归测试。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from plc_gateway.config import GatewayConfig
from plc_gateway.policy.risk_levels import RiskLevel
from plc_gateway.policy.routing import RoutingPolicy
from plc_gateway.providers.base import ErrorInfo, ProviderResult
from plc_gateway.providers.tiaworker import TiaWorkerProvider


PROJECT_PATH = r"D:\PLC\demo_V21.ap21"


def _client(response: dict) -> MagicMock:
    client = MagicMock()
    client.available = True
    client.run.return_value = response
    return client


def test_tiaworker_provider_uses_shared_client_and_unified_project_path():
    client = _client({"success": True, "data": {"blocks": []}})
    provider = TiaWorkerProvider(client, PROJECT_PATH)

    result = provider.list_blocks()

    assert result.ok is True
    client.run.assert_called_once_with(
        "list-blocks", {"ProjectPath": PROJECT_PATH}, max_retries=1
    )


def test_tiaworker_provider_uses_verified_read_command_and_v21_client():
    client = _client({"success": True, "data": {"devices": []}})
    provider = TiaWorkerProvider(client, PROJECT_PATH)

    result = provider.list_devices()

    assert result.ok is True
    client.run.assert_called_once_with(
        "list-devices", {"ProjectPath": PROJECT_PATH}, max_retries=1
    )


def test_tiaworker_xml_is_unavailable_until_export_protocol_is_verified():
    provider = TiaWorkerProvider(_client({}), PROJECT_PATH)

    result = provider.get_block_xml("FB1")

    assert result.status == "unavailable"
    assert result.error.code == "CAPABILITY_UNAVAILABLE"


def test_provider_error_contract_is_always_serializable_and_never_treats_output_as_success():
    client = _client({"success": False, "output": "warning without success"})
    provider = TiaWorkerProvider(client, PROJECT_PATH)

    result = provider.get_project_info()

    assert result.ok is False
    assert result.to_dict()["error"]["code"] == "TIA_EXEC_ERROR"
    assert ProviderResult(ok=False, operation="x", provider="p", error="bad").to_dict()["error"] == {
        "code": "ERROR", "message": "bad", "retryable": False, "side_effect_state": "none"
    }
    assert ErrorInfo(code="E", message="bad").to_dict()["code"] == "E"


def test_reconcile_required_has_a_distinct_status_and_unknown_side_effect():
    result = ProviderResult.error_result(
        "tia.block.list", "timeout", reconcile_required=True, provider="tiaworker"
    )

    assert result.status == "reconcile_required"
    assert result.to_dict()["error"]["side_effect_state"] == "unknown"


def test_registry_uses_the_single_policy_risk_level():
    from plc_gateway.registry import RiskLevel as RegistryRiskLevel

    assert RegistryRiskLevel is RiskLevel


def test_gateway_rejects_a_non_v21_target_config(monkeypatch):
    target = MagicMock(project_path=PROJECT_PATH, tia_version="V18", profile="isolated_plcsim_v21")
    monkeypatch.setattr("plc_gateway.config.load_yaml_config", lambda _path: MagicMock(target=target))

    with pytest.raises(ValueError, match="V21"):
        GatewayConfig.from_env()


def test_default_read_provider_is_honored_without_fallback():
    class Provider:
        def __init__(self, name, available):
            self.name = name
            self.available = available

    tiaworker = Provider("tiaworker", True)
    tiacommander = Provider("tiacommander", False)
    policy = RoutingPolicy(default_read="tiacommander")
    policy.register_provider(tiaworker)
    policy.register_provider(tiacommander)

    assert policy.get_read_provider() is tiacommander


def test_gateway_rejects_tiacommander_as_default_read_provider_without_identity_support():
    from plc_gateway.bootstrap import bootstrap_gateway

    with pytest.raises(RuntimeError, match="身份校验"):
        bootstrap_gateway(GatewayConfig(default_read_provider="tiacommander"))
