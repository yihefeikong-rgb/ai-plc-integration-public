"""
MCP 服务器/工具注册表。

管理所有 MCP 服务器的工具清单，提供按名称查找和工具发现。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


# ============================================================================
# 工具分类常量
# ============================================================================

TOOL_CATEGORIES: dict[str, str] = {
    "s7": "S7 运行态读写",
    "tia": "TIA 工程态操作",
    "safety": "安全相关",
    "monitoring": "监控/采集",
    "control": "控制指令",
    "engineering": "工程配置",
    "desktop": "桌面控制",
    "pipeline": "流水线",
    "uncategorized": "未分类",
}


def categorize_tool(server_name: str, tool_name: str) -> str:
    """根据服务器名和工具名推断工具分类。

    优先按服务器名匹配，再按工具名关键词匹配，
    都不命中则返回 "uncategorized"。
    """
    # 按服务器名直接映射
    server_map = {
        "desktop-mcp": "desktop",
        "plc-mcp-bridge": "s7",
        "tia-mcp": "tia",
        "opcua-mcp": "monitoring",
        "modbus-mcp": "monitoring",
        "mitsubishi-mcp": "s7",
        "robot-mcp": "control",
    }
    if server_name in server_map:
        return server_map[server_name]

    # 按工具名关键词匹配
    name_lower = tool_name.lower()
    if any(kw in name_lower for kw in ("s7_", "s7read", "s7write")):
        return "s7"
    if any(kw in name_lower for kw in ("safety", "interlock", "shadow_sim", "audit", "fuse")):
        return "safety"
    if any(kw in name_lower for kw in ("tia_", "compile", "download", "upload")):
        return "tia"
    if any(kw in name_lower for kw in ("screenshot", "click", "type_text", "hotkey",
                                        "scroll", "drag", "press_key", "move_mouse",
                                        "mouse_position", "screen_size", "locate_on_screen",
                                        "double_click", "right_click")):
        return "desktop"
    if any(kw in name_lower for kw in ("pipeline", "run_pipeline")):
        return "pipeline"
    if any(kw in name_lower for kw in ("monitor", "read", "watch", "status", "collect")):
        return "monitoring"
    if any(kw in name_lower for kw in ("write", "set", "control", "start", "stop")):
        return "control"

    return "uncategorized"


@dataclass
class ToolInfo:
    """MCP 工具元数据"""
    name: str
    description: str = ""
    server: str = ""  # 所属 MCP 服务器
    parameters: dict[str, Any] = field(default_factory=dict)
    category: str = "uncategorized"


@dataclass
class ServerInfo:
    """MCP 服务器元数据"""
    name: str
    description: str = ""
    protocol: str = "stdio"  # stdio | jsonrpc
    command: str = ""  # 启动命令（如 "python"）
    args: list[str] = field(default_factory=list)  # 启动参数（如 ["server.py"]）
    cwd: str = ""  # 工作目录
    tools: list[ToolInfo] = field(default_factory=list)
    credential_envs: tuple[str, ...] = ()
    credential_argument: str = "auth_token"


class Registry:
    """MCP 服务器和工具注册表。

    维护所有 MCP 服务器的工具清单，支持按名称查找工具。
    骨架阶段为内存注册表，后续可扩展为服务发现。
    """

    def __init__(self):
        self._servers: dict[str, ServerInfo] = {}
        self._tools: dict[str, ToolInfo] = {}  # 按 "server.tool" 全名索引

    def register_server(self, server: ServerInfo) -> None:
        """注册一个 MCP 服务器及其工具
        重复注册同名服务器会覆盖旧数据。
        """
        # 清除旧工具
        if server.name in self._servers:
            old_tools = self._servers[server.name].tools
            for old_tool in old_tools:
                full_name = f"{server.name}.{old_tool.name}"
                self._tools.pop(full_name, None)

        self._servers[server.name] = server
        for tool in server.tools:
            tool.server = server.name
            if tool.category == "uncategorized":
                tool.category = categorize_tool(server.name, tool.name)
            full_name = f"{server.name}.{tool.name}"
            self._tools[full_name] = tool

    def register_tool(self, server_name: str, tool: ToolInfo) -> None:
        """注册单个工具到指定服务器"""
        tool.server = server_name
        if tool.category == "uncategorized":
            tool.category = categorize_tool(server_name, tool.name)
        full_name = f"{server_name}.{tool.name}"
        self._tools[full_name] = tool
        if server_name in self._servers:
            self._servers[server_name].tools.append(tool)

    def get_tool(self, full_name: str) -> ToolInfo | None:
        """按完整名称查找工具，如 'tia-mcp.compile_project'"""
        return self._tools.get(full_name)

    def get_server(self, name: str) -> ServerInfo | None:
        """按名称查找服务器"""
        return self._servers.get(name)

    def list_servers(self) -> list[str]:
        """列出所有已注册的服务器"""
        return list(self._servers.keys())

    def list_tools(self, server_name: str | None = None) -> list[ToolInfo]:
        """列出工具，可按服务器过滤"""
        if server_name:
            server = self._servers.get(server_name)
            return list(server.tools) if server else []
        return list(self._tools.values())

    def tool_count(self) -> int:
        """已注册工具总数"""
        return len(self._tools)

    def server_count(self) -> int:
        """已注册服务器总数"""
        return len(self._servers)


# 全局单例
_registry = Registry()


def get_registry() -> Registry:
    """获取全局注册表单例"""
    return _registry
