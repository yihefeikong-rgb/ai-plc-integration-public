"""
预注册 MCP 服务器配置。

定义各 MCP 服务器的启动参数（command/args/cwd），
供编排层在连接真实 MCP 服务器时使用。
"""

import os
import sys
from pathlib import Path

from orchestrator.registry import ServerInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_EXECUTABLE = sys.executable


def _server_cwd(*parts: str) -> str:
    return str(PROJECT_ROOT.joinpath(*parts))

# ============================================================================
# MCP 服务器配置
# ============================================================================

PLC_MCP_BRIDGE = ServerInfo(
    name="plc-mcp-bridge",
    description="S7 运行态读写 + TIA 工程态 + PLCSIM + FIO 配置（65 工具）",
    command=PYTHON_EXECUTABLE,
    args=["server.py"],
    cwd=_server_cwd("mcp-servers", "plc-mcp-bridge"),
)

TIA_MCP = ServerInfo(
    name="tia-mcp",
    description="TIA Portal Openness 工程态操作（16 工具）",
    command=PYTHON_EXECUTABLE,
    args=["server.py"],
    cwd=_server_cwd("mcp-servers", "tia-mcp"),
    credential_envs=("TIA_MCP_AUTH_TOKEN", "MCP_AUTH_TOKEN"),
)

OPCUA_MCP = ServerInfo(
    name="opcua-mcp",
    description="OPC UA 协议读写（7 工具）",
    command=PYTHON_EXECUTABLE,
    args=["server.py"],
    cwd=_server_cwd("mcp-servers", "opcua-mcp"),
    credential_envs=("MCP_AUTH_TOKEN",),
)

MODBUS_MCP = ServerInfo(
    name="modbus-mcp",
    description="Modbus TCP 协议读写（6 工具）",
    command=PYTHON_EXECUTABLE,
    args=["server.py"],
    cwd=_server_cwd("mcp-servers", "modbus-mcp"),
    credential_envs=("MCP_AUTH_TOKEN",),
)

MITSUBISHI_MCP = ServerInfo(
    name="mitsubishi-mcp",
    description="三菱 MC 协议读写（3 工具）",
    command=PYTHON_EXECUTABLE,
    args=["server.py"],
    cwd=_server_cwd("mcp-servers", "mitsubishi-mcp"),
    credential_envs=("MCP_AUTH_TOKEN",),
)

ROBOT_MCP = ServerInfo(
    name="robot-mcp",
    description="工业机器人控制 — FIO Pick & Place（7 工具）",
    command=PYTHON_EXECUTABLE,
    args=["server.py"],
    cwd=_server_cwd("mcp-servers", "robot-mcp"),
    credential_envs=("MCP_AUTH_TOKEN",),
)

DESKTOP_MCP = ServerInfo(
    name="desktop-mcp",
    description="桌面控制 — 鼠标键盘 + 截图（13 工具）",
    command=PYTHON_EXECUTABLE,
    args=["server.py"],
    cwd=_server_cwd("mcp-servers", "desktop-mcp"),
)

# ============================================================================
# PLC Engineering Gateway — 阴影模式
# ============================================================================
# PLC_GATEWAY_MODE 环境变量控制：
#   shadow (默认) — 启动但不参与主路由，仅用于比较验证
#   off — 不启动
#   primary — 正式接管 TIA 工程态操作（需显式设置）
_GATEWAY_MODE = os.environ.get("PLC_GATEWAY_MODE", "shadow")

PLC_GATEWAY = ServerInfo(
    name="plc-gateway",
    description="PLC Engineering Gateway — 统一工程态网关（阴影模式，9 工具）",
    command=PYTHON_EXECUTABLE,
    args=["-m", "plc_gateway.server"],
    cwd=str(PROJECT_ROOT),
)

# ============================================================================
# 集成测试用服务器
# ============================================================================

TEST_ECHO = ServerInfo(
    name="test-echo",
    description="集成测试用最小 MCP 服务器（3 工具）",
    command=PYTHON_EXECUTABLE,
    args=[str(PROJECT_ROOT / "orchestrator" / "tests" / "test_echo_server.py")],
    cwd=str(PROJECT_ROOT),
)

# ============================================================================
# 所有服务器的列表
# ============================================================================

ALL_SERVERS: list[ServerInfo] = [
    PLC_MCP_BRIDGE,
    TIA_MCP,
    OPCUA_MCP,
    MODBUS_MCP,
    MITSUBISHI_MCP,
    ROBOT_MCP,
    # DESKTOP_MCP — 使用非标准 JSON-RPC，不兼容 MCP 协议，暂不自动连接
    # TEST_ECHO — 仅用于集成测试，不自动连接
]

# 阴影模式服务器列表（仅用于比较，不影响主流程）
SHADOW_SERVERS: list[ServerInfo] = []
if _GATEWAY_MODE == "shadow":
    SHADOW_SERVERS = [PLC_GATEWAY]
elif _GATEWAY_MODE == "primary":
    SHADOW_SERVERS = []
    ALL_SERVERS.append(PLC_GATEWAY)

# 按名称快速查找
SERVER_MAP: dict[str, ServerInfo] = {s.name: s for s in ALL_SERVERS}


def get_server_config(name: str) -> ServerInfo | None:
    """按名称获取服务器配置"""
    return SERVER_MAP.get(name)


def list_server_names() -> list[str]:
    """列出所有已配置的服务器名称"""
    return [s.name for s in ALL_SERVERS]
