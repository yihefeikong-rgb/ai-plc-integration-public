"""Gateway 实际 TIA 项目身份校验的离线测试。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from plc_gateway.providers.base import ProviderResult
from plc_gateway.providers.tiaworker import TiaWorkerProvider


PROJECT_PATH = r"D:\PLC\demo_V21.ap21"


def _provider(project_info: object) -> tuple[TiaWorkerProvider, MagicMock]:
    client = MagicMock()
    client.available = True
    client.run.return_value = {"success": True, "data": project_info}
    return TiaWorkerProvider(client, PROJECT_PATH), client


def test_identity_accepts_case_and_trailing_separator_variants():
    provider, _ = _provider({"path": r"d:\plc\demo_v21.ap21"})

    assert provider.verify_target_identity().ok is True


@pytest.mark.parametrize("project_info", [
    {"path": r"D:\PLC\other.ap21"},
    {"path": "demo_V21.ap21"},
    {"path": ""},
    {},
    None,
])
def test_identity_rejects_missing_relative_or_mismatched_actual_path(project_info):
    provider, _ = _provider(project_info)

    result = provider.verify_target_identity()

    assert result.ok is False
    assert result.error.code == "TARGET_MISMATCH"


def test_identity_propagates_project_info_failure():
    provider, client = _provider({})
    client.run.return_value = {"success": False, "error": "worker failed"}

    result = provider.verify_target_identity()

    assert result.ok is False
    assert result.error.code == "TIA_EXEC_ERROR"


def test_read_endpoint_does_not_call_business_operation_after_identity_failure(monkeypatch):
    from plc_gateway import server

    provider = MagicMock()
    provider.verify_target_identity.return_value = ProviderResult.error_result(
        "tia.project.verify_identity", "mismatch", code="TARGET_MISMATCH", provider="tiaworker", status="blocked"
    )
    monkeypatch.setattr(server, "_get_read_provider", lambda: (provider, None))

    result = server.tia_block_list()

    assert result["error"]["code"] == "TARGET_MISMATCH"
    provider.list_blocks.assert_not_called()
