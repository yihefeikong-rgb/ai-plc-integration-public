import pytest
from pathlib import Path

from mcp_common.control_target import (
    approved_opcua_endpoint,
    require_control_ip,
    require_opcua_endpoint,
)
from config_loader import TargetConfigurationError


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_control_target_helpers_only_accept_the_configured_isolated_target():
    target = require_control_ip("192.168.0.1")

    assert target.plcsim_instance == "factoryio"
    assert approved_opcua_endpoint() == "opc.tcp://192.168.0.1:4840"
    assert require_opcua_endpoint("opc.tcp://192.168.0.1:4840") == target


@pytest.mark.parametrize(
    ("ip", "endpoint", "reject_ip", "reject_endpoint"),
    [
        ("192.168.0.110", "opc.tcp://192.168.0.1:4840", True, False),
        ("192.168.0.1", "opc.tcp://192.168.0.110:4840", False, True),
        ("192.168.0.1", "opc.tcp://192.168.0.1:4841", False, True),
    ],
)
def test_control_target_helpers_reject_drift(ip, endpoint, reject_ip, reject_endpoint):
    if reject_ip:
        with pytest.raises(TargetConfigurationError):
            require_control_ip(ip)
    else:
        require_control_ip(ip)
    if reject_endpoint:
        with pytest.raises(TargetConfigurationError):
            require_opcua_endpoint(endpoint)
    else:
        require_opcua_endpoint(endpoint)


def test_runtime_control_entrypoints_delegate_target_selection_to_the_contract():
    source_files = [
        PROJECT_ROOT / "mcp-servers" / "plc-mcp-bridge" / "tools_s7.py",
        PROJECT_ROOT / "mcp-servers" / "plc-mcp-bridge" / "s7_adapter.py",
        PROJECT_ROOT / "mcp-servers" / "plc-mcp-bridge" / "tools_plcsim.py",
        PROJECT_ROOT / "mcp-servers" / "opcua-mcp" / "server.py",
        PROJECT_ROOT / "mcp-servers" / "robot-mcp" / "server.py",
        PROJECT_ROOT / "mcp-servers" / "robot-mcp" / "deploy_pnp.py",
        PROJECT_ROOT / "mcp-servers" / "robot-mcp" / "verify_pick_and_place.py",
        PROJECT_ROOT / "mcp-servers" / "tia-mcp" / "plcsim_api.py",
        PROJECT_ROOT / "mcp-servers" / "tia-mcp" / "plcsim_instance.py",
        PROJECT_ROOT / "mcp-servers" / "tia-mcp" / "plcsim_backup.py",
        PROJECT_ROOT / "mcp-servers" / "tia-mcp" / "plcsim_network.py",
    ]

    for path in source_files:
        content = path.read_text(encoding="utf-8")
        assert '"192.168.0.110"' not in content, path

    for path in source_files:
        content = path.read_text(encoding="utf-8")
        if path.name not in {"plcsim_backup.py", "deploy_pnp.py", "verify_pick_and_place.py"}:
            assert "mcp_common.control_target" in content, path
