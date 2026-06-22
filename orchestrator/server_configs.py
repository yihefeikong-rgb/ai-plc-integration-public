"""
预注册 MCP 服务器配置。

定义各 MCP 服务器的启动参数（command/args/cwd），
供编排层在连接真实 MCP 服务器时使用。
"""

from orchestrator.registry import ServerInfo

# ============================================================================
# MCP 服务器配置
# ============================================================================

PLC_MCP_BRIDGE = ServerInfo(
    name="plc-mcp-bridge",
    description="S7 运行态读写 + TIA 工程态 + PLCSIM + FIO 配置（65 工具）",
    command=r"D:\Python3\python.exe",
    args=["server.py"],
    cwd=r"D:\claude code xiangmu\AI 接入PLC\mcp-servers\plc-mcp-bridge",
)

TIA_MCP = ServerInfo(
    name="tia-mcp",
    description="TIA Portal Openness 工程态操作（16 工具）",
    command=r"D:\Python3\python.exe",
    args=["server.py"],
    cwd=r"D:\claude code xiangmu\AI 接入PLC\mcp-servers\tia-mcp",
)

OPCUA_MCP = ServerInfo(
    name="opcua-mcp",
    description="OPC UA 协议读写（7 工具）",
    command=r"D:\Python3\python.exe",
    args=["server.py"],
    cwd=r"D:\claude code xiangmu\AI 接入PLC\mcp-servers\opcua-mcp",
)

MODBUS_MCP = ServerInfo(
    name="modbus-mcp",
    description="Modbus TCP 协议读写（6 工具）",
    command=r"D:\Python3\python.exe",
    args=["server.py"],
    cwd=r"D:\claude code xiangmu\AI 接入PLC\mcp-servers\modbus-mcp",
)

MITSUBISHI_MCP = ServerInfo(
    name="mitsubishi-mcp",
    description="三菱 MC 协议读写（3 工具）",
    command=r"D:\Python3\python.exe",
    args=["server.py"],
    cwd=r"D:\claude code xiangmu\AI 接入PLC\mcp-servers\mitsubishi-mcp",
)

ROBOT_MCP = ServerInfo(
    name="robot-mcp",
    description="工业机器人控制 — FIO Pick & Place（7 工具）",
    command=r"D:\Python3\python.exe",
    args=["server.py"],
    cwd=r"D:\claude code xiangmu\AI 接入PLC\mcp-servers\robot-mcp",
)

DESKTOP_MCP = ServerInfo(
    name="desktop-mcp",
    description="桌面控制 — 鼠标键盘 + 截图（13 工具）",
    command=r"D:\Python3\python.exe",
    args=["server.py"],
    cwd=r"D:\claude code xiangmu\AI 接入PLC\mcp-servers\desktop-mcp",
)

# ============================================================================
# 集成测试用服务器
# ============================================================================

TEST_ECHO = ServerInfo(
    name="test-echo",
    description="集成测试用最小 MCP 服务器（3 工具）",
    command=r"D:\Python3\python.exe",
    args=[r"orchestrator\tests\test_echo_server.py"],
    cwd=r"D:\claude code xiangmu\AI 接入PLC",
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

# 按名称快速查找
SERVER_MAP: dict[str, ServerInfo] = {s.name: s for s in ALL_SERVERS}


def get_server_config(name: str) -> ServerInfo | None:
    """按名称获取服务器配置"""
    return SERVER_MAP.get(name)


def list_server_names() -> list[str]:
    """列出所有已配置的服务器名称"""
    return [s.name for s in ALL_SERVERS]
