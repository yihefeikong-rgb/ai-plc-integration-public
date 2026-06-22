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
    description="S7 运行态读写 + TIA 工程态 + PLCSIM + FIO 配置",
    command="D:\\Python3\\python.exe",
    args=["server.py"],
    cwd="D:\\claude code xiangmu\\AI 接入PLC\\mcp-servers\\plc-mcp-bridge",
)

TIA_MCP = ServerInfo(
    name="tia-mcp",
    description="TIA Portal Openness 工程态操作（编译/下载/导入）",
    command="D:\\Python3\\python.exe",
    args=["server.py"],
    cwd="D:\\claude code xiangmu\\AI 接入PLC\\mcp-servers\\tia-mcp",
)

# ============================================================================
# 所有服务器的列表
# ============================================================================

ALL_SERVERS: list[ServerInfo] = [
    PLC_MCP_BRIDGE,
    TIA_MCP,
]

# 按名称快速查找
SERVER_MAP: dict[str, ServerInfo] = {s.name: s for s in ALL_SERVERS}


def get_server_config(name: str) -> ServerInfo | None:
    """按名称获取服务器配置"""
    return SERVER_MAP.get(name)