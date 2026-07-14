"""唯一隔离控制目标的跨 MCP 访问入口。"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_TIA_MCP_DIR = _PROJECT_ROOT / "mcp-servers" / "tia-mcp"
if str(_TIA_MCP_DIR) not in sys.path:
    sys.path.insert(0, str(_TIA_MCP_DIR))

from config_loader import ControlTarget, TargetConfigurationError, validate_control_target


OPCUA_PORT = 4840


def get_control_target() -> ControlTarget:
    """读取并验证唯一 V21 / 隔离 PLCSIM 目标。"""
    return validate_control_target()


def require_control_ip(ip: str) -> ControlTarget:
    """拒绝绕开 target 配置的 S7/PLCSIM IP。"""
    target = get_control_target()
    if ip != target.plc_ip:
        raise TargetConfigurationError(
            f"控制 IP 必须为唯一隔离目标 {target.plc_ip}，收到 {ip}"
        )
    return target


def approved_opcua_endpoint() -> str:
    """返回唯一目标的固定 OPC UA 端点。"""
    return f"opc.tcp://{get_control_target().plc_ip}:{OPCUA_PORT}"


def require_opcua_endpoint(endpoint: str) -> ControlTarget:
    """只允许连接唯一目标的默认 OPC UA 端口。"""
    target = get_control_target()
    parsed = urlparse(endpoint)
    if (
        parsed.scheme != "opc.tcp"
        or parsed.hostname != target.plc_ip
        or parsed.port != OPCUA_PORT
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise TargetConfigurationError(
            f"OPC UA 端点必须为 {approved_opcua_endpoint()}，收到 {endpoint}"
        )
    return target
