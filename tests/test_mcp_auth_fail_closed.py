import importlib.util
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent


def load_server(module_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(module_name, PROJECT_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(("module_name", "relative_path"), [
    ("opcua_auth_server", "mcp-servers/opcua-mcp/server.py"),
    ("robot_auth_server", "mcp-servers/robot-mcp/server.py"),
])
def test_mcp_control_authentication_fails_closed_when_token_is_unconfigured(
    monkeypatch, module_name, relative_path,
):
    module = load_server(module_name, relative_path)
    monkeypatch.setattr(module, "_AUTH_TOKEN", "")

    with pytest.raises(PermissionError, match="MCP_AUTH_TOKEN"):
        module._require_auth("")
