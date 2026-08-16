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


@pytest.mark.parametrize("bad_token", ["中文令牌", "tokén", "\u00e9"])
def test_non_ascii_tokens_are_rejected_without_type_error(bad_token):
    """非 ASCII str 令牌必须被拒绝而不是让 hmac.compare_digest 抛 TypeError。"""
    module = load_server("opcua_auth_server_ascii", "mcp-servers/opcua-mcp/server.py")
    assert module._AUTH_TOKEN, "conftest 应已设置 MCP_AUTH_TOKEN"
    with pytest.raises(PermissionError, match="认证失败"):
        module._require_auth(bad_token)


def test_modbus_non_ascii_and_non_string_tokens_rejected():
    module = load_server("modbus_auth_server_ascii", "mcp-servers/modbus-mcp/server.py")
    assert module._AUTH_TOKEN, "conftest 应已设置 MCP_AUTH_TOKEN"
    with pytest.raises(PermissionError, match="认证失败"):
        module._require_auth("中文令牌")
    with pytest.raises(PermissionError, match="认证失败"):
        module._require_auth(b"bytes-token")


def test_mitsubishi_non_ascii_token_rejected():
    module = load_server("mitsubishi_auth_server_ascii", "mcp-servers/mitsubishi-mcp/server.py")
    assert module._AUTH_TOKEN, "conftest 应已设置 MCP_AUTH_TOKEN"
    with pytest.raises(PermissionError, match="认证失败"):
        module._require_auth("中文令牌")
