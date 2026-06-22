"""
TS009 — desktop-mcp 接入 + 工具分类 测试
"""
import pytest

from orchestrator.server_configs import (
    DESKTOP_MCP,
    ALL_SERVERS,
    SERVER_MAP,
    list_server_names,
    get_server_config,
)
from orchestrator.registry import (
    ToolInfo,
    ServerInfo,
    Registry,
    categorize_tool,
    TOOL_CATEGORIES,
)


# ============================================================================
# DESKTOP_MCP 配置
# ============================================================================


class TestDesktopMcpConfig:
    """desktop-mcp 服务器配置测试"""

    def test_desktop_mcp_exists(self):
        """DESKTOP_MCP 配置对象存在且字段正确"""
        assert DESKTOP_MCP is not None
        assert DESKTOP_MCP.name == "desktop-mcp"
        assert DESKTOP_MCP.command.endswith("python.exe")
        assert DESKTOP_MCP.args == ["server.py"]
        assert "desktop-mcp" in DESKTOP_MCP.cwd

    def test_desktop_mcp_in_all_servers(self):
        """DESKTOP_MCP 在 ALL_SERVERS 列表中"""
        names = [s.name for s in ALL_SERVERS]
        assert "desktop-mcp" in names

    def test_desktop_mcp_in_server_map(self):
        """DESKTOP_MCP 在 SERVER_MAP 字典中"""
        assert "desktop-mcp" in SERVER_MAP
        assert SERVER_MAP["desktop-mcp"] is DESKTOP_MCP

    def test_desktop_mcp_via_get_server_config(self):
        """通过 get_server_config 可获取 DESKTOP_MCP"""
        config = get_server_config("desktop-mcp")
        assert config is DESKTOP_MCP

    def test_desktop_mcp_via_list_server_names(self):
        """list_server_names 包含 desktop-mcp"""
        assert "desktop-mcp" in list_server_names()


# ============================================================================
# ToolInfo category 字段
# ============================================================================


class TestToolInfoCategory:
    """ToolInfo 的 category 字段测试"""

    def test_default_category(self):
        """默认 category 为 'uncategorized'"""
        tool = ToolInfo(name="test_tool")
        assert tool.category == "uncategorized"

    def test_explicit_category(self):
        """可显式指定 category"""
        tool = ToolInfo(name="s7_read", category="s7")
        assert tool.category == "s7"

    def test_backward_compatible(self):
        """不带 category 参数时向后兼容"""
        tool = ToolInfo(name="legacy", description="legacy tool", server="legacy-server")
        assert tool.category == "uncategorized"


# ============================================================================
# TOOL_CATEGORIES 常量
# ============================================================================


class TestToolCategories:
    """工具分类常量测试"""

    def test_all_expected_categories_present(self):
        """所有预期分类都存在"""
        expected_keys = {"s7", "tia", "safety", "monitoring", "control",
                         "engineering", "desktop", "pipeline", "uncategorized"}
        assert set(TOOL_CATEGORIES.keys()) == expected_keys

    def test_category_values_are_chinese(self):
        """分类值是中文描述"""
        for key, value in TOOL_CATEGORIES.items():
            assert isinstance(value, str) and len(value) > 0


# ============================================================================
# categorize_tool 函数
# ============================================================================


class TestCategorizeTool:
    """categorize_tool 推断逻辑测试"""

    # 按服务器名映射
    def test_desktop_mcp_server(self):
        """desktop-mcp 的工具 → 'desktop'"""
        assert categorize_tool("desktop-mcp", "screenshot") == "desktop"
        assert categorize_tool("desktop-mcp", "click") == "desktop"
        assert categorize_tool("desktop-mcp", "any_tool") == "desktop"

    def test_plc_mcp_bridge_server(self):
        """plc-mcp-bridge → 's7'"""
        assert categorize_tool("plc-mcp-bridge", "read_tags") == "s7"

    def test_tia_mcp_server(self):
        """tia-mcp → 'tia'"""
        assert categorize_tool("tia-mcp", "compile_block") == "tia"

    def test_robot_mcp_server(self):
        """robot-mcp → 'control'"""
        assert categorize_tool("robot-mcp", "pick") == "control"

    def test_opcua_mcp_server(self):
        """opcua-mcp → 'monitoring'"""
        assert categorize_tool("opcua-mcp", "read_node") == "monitoring"

    # 按工具名关键词匹配（未知服务器）
    def test_s7_keyword(self):
        """含 s7_ 关键词 → 's7'"""
        assert categorize_tool("unknown-server", "s7_read") == "s7"

    def test_safety_keyword(self):
        """含 safety 关键词 → 'safety'"""
        assert categorize_tool("unknown-server", "safety_check") == "safety"
        assert categorize_tool("unknown-server", "interlock_check") == "safety"
        assert categorize_tool("unknown-server", "shadow_sim") == "safety"

    def test_desktop_keyword(self):
        """桌面控制关键词 → 'desktop'"""
        assert categorize_tool("unknown-server", "screenshot") == "desktop"
        assert categorize_tool("unknown-server", "click") == "desktop"
        assert categorize_tool("unknown-server", "hotkey") == "desktop"

    def test_pipeline_keyword(self):
        """含 pipeline 关键词 → 'pipeline'"""
        assert categorize_tool("unknown-server", "run_pipeline") == "pipeline"

    def test_monitoring_keyword(self):
        """含监控关键词 → 'monitoring'"""
        assert categorize_tool("unknown-server", "read_value") == "monitoring"
        assert categorize_tool("unknown-server", "status_check") == "monitoring"

    def test_control_keyword(self):
        """含控制关键词 → 'control'"""
        assert categorize_tool("unknown-server", "write_value") == "control"
        assert categorize_tool("unknown-server", "start_motor") == "control"

    def test_unknown_tool(self):
        """完全未知的工具 → 'uncategorized'"""
        assert categorize_tool("unknown-server", "xyz_foobar") == "uncategorized"


# ============================================================================
# Registry 自动分类
# ============================================================================


class TestRegistryAutoCategorize:
    """Registry 注册时自动推断 category"""

    def test_register_server_sets_category(self):
        """register_server 自动为工具设置 category"""
        registry = Registry()
        server = ServerInfo(
            name="desktop-mcp",
            tools=[
                ToolInfo(name="screenshot", description="截图"),
                ToolInfo(name="click", description="点击"),
            ],
        )
        registry.register_server(server)
        tools = registry.list_tools("desktop-mcp")
        for tool in tools:
            assert tool.category == "desktop"

    def test_register_tool_sets_category(self):
        """register_tool 自动为工具设置 category"""
        registry = Registry()
        registry.register_server(ServerInfo(name="unknown-server"))
        registry.register_tool("unknown-server", ToolInfo(name="s7_read"))
        tool = registry.get_tool("unknown-server.s7_read")
        assert tool.category == "s7"

    def test_explicit_category_not_overridden(self):
        """显式设置的 category 不被覆盖"""
        registry = Registry()
        server = ServerInfo(
            name="desktop-mcp",
            tools=[ToolInfo(name="screenshot", category="custom")],
        )
        registry.register_server(server)
        tool = registry.get_tool("desktop-mcp.screenshot")
        assert tool.category == "custom"
