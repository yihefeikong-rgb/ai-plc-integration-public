"""PLC Gateway — Batch 3 验收测试（可从仓库根目录运行）。"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch


def test_config_defaults():
    from plc_gateway.config import GatewayConfig
    cfg = GatewayConfig()
    assert cfg.tia_version == "V21"
    assert cfg.safety_enabled is True
    assert cfg.tiacommander_enabled is False
    assert cfg.default_read_provider == "tiaworker"


def test_config_from_unified_target():
    os.environ["GATEWAY_TIACOMMANDER_ENABLED"] = "1"
    os.environ["GATEWAY_SAFETY_ENABLED"] = "0"
    os.environ["GATEWAY_DEBUG"] = "1"

    from plc_gateway.config import GatewayConfig
    target = SimpleNamespace(
        project_path="D:/test/demo_V21.ap21",
        tia_version="V21",
        profile="isolated_plcsim_v21",
    )
    with patch("plc_gateway.config.load_yaml_config", return_value=SimpleNamespace(target=target)):
        cfg = GatewayConfig.from_env()
    assert cfg.target_project == "D:/test/demo_V21.ap21"
    assert cfg.tia_version == "V21"
    assert cfg.target_profile == "isolated_plcsim_v21"
    assert cfg.tiacommander_enabled is True
    assert cfg.safety_enabled is False
    assert cfg.debug is True

    for k in ["GATEWAY_TIACOMMANDER_ENABLED", "GATEWAY_SAFETY_ENABLED",
              "GATEWAY_DEBUG"]:
        os.environ.pop(k, None)


def test_config_to_dict():
    from plc_gateway.config import GatewayConfig
    cfg = GatewayConfig(target_project="/test")
    d = cfg.to_dict()
    assert d["target_configured"] is True
    assert "target_project" not in d
    assert d["tia_version"] == "V21"
    assert "safety_enabled" in d


def test_bootstrap_context():
    from plc_gateway.config import GatewayConfig
    from plc_gateway.bootstrap import bootstrap_gateway

    cfg = GatewayConfig(safety_enabled=True, debug=True)
    ctx = bootstrap_gateway(cfg)
    assert ctx.gateway_id is not None
    assert len(ctx.gateway_id) == 8
    assert ctx.config is cfg
    assert ctx.registry is not None
    assert ctx.safety is not None
    assert ctx.routing is not None


def test_bootstrap_context_disabled_safety():
    from plc_gateway.config import GatewayConfig
    from plc_gateway.bootstrap import bootstrap_gateway

    cfg = GatewayConfig(safety_enabled=False, debug=True)
    ctx = bootstrap_gateway(cfg)
    assert ctx.safety is None


def test_bootstrap_registers_tools():
    from plc_gateway.config import GatewayConfig
    from plc_gateway.bootstrap import bootstrap_gateway

    cfg = GatewayConfig(debug=True)
    ctx = bootstrap_gateway(cfg)
    assert len(ctx.registry) == 34, f"预期 34 个工具，实际 {len(ctx.registry)}"


def test_bootstrap_context_to_dict():
    from plc_gateway.config import GatewayConfig
    from plc_gateway.bootstrap import bootstrap_gateway

    cfg = GatewayConfig(debug=True)
    ctx = bootstrap_gateway(cfg)
    d = ctx.to_dict()
    assert "gateway_id" in d
    assert "config" in d
    assert "providers" in d
    assert "tools_count" in d
    assert "safety_enabled" in d
    assert d["tools_count"] == 34


def test_bootstrap_provider_info():
    from plc_gateway.config import GatewayConfig
    from plc_gateway.bootstrap import bootstrap_gateway

    cfg = GatewayConfig(debug=True)
    ctx = bootstrap_gateway(cfg)
    info = ctx.get_provider_info()
    assert len(info) > 0
    for p in info:
        assert "name" in p
        assert "configured" in p
        assert "available" in p
        assert "read_enabled" in p
        assert "write_enabled" in p


def test_bootstrap_list_capabilities():
    from plc_gateway.config import GatewayConfig
    from plc_gateway.bootstrap import bootstrap_gateway

    cfg = GatewayConfig(debug=True)
    ctx = bootstrap_gateway(cfg)
    caps = ctx.list_capabilities()
    assert caps["declared_count"] == len(caps["exposed"])
    assert {"gateway.get_info", "gateway.list_providers", "gateway.list_capabilities"}.issubset(caps["available"])
    assert "tia.block.list" in caps["exposed"]
    assert "tia.block.get_xml" in caps["exposed"]
    assert "tia.project.list" in caps["exposed"]
    assert "tia.hardware.list" in caps["exposed"]


def test_server_fastmcp_tools():
    import asyncio
    from plc_gateway.server import mcp, get_context

    ctx = get_context()
    assert ctx is not None

    async def _list():
        tools = await mcp.list_tools()
        return tools

    tools = asyncio.run(_list())
    assert len(tools) >= 8

    tool_names = [t.name for t in tools]
    assert "gateway.get_info" in tool_names
    assert "gateway.list_providers" in tool_names
    assert "gateway.list_capabilities" in tool_names
    assert "tia.project.info" in tool_names
    assert "tia.block.list" in tool_names
    assert "tia.block.get_xml" in tool_names
    assert "tia.block.get_interface" in tool_names
    assert "tia.hardware.list" in tool_names


def test_unavailable_provider():
    from plc_gateway.bootstrap import _UnavailableProvider

    p = _UnavailableProvider("test")
    assert p.name == "test"
    assert p.available is False
    assert p.read_only is True

    result = p.get_project_info()
    assert result.ok is False
    assert "不可用" in (result.error.message if result.error else "")

    result = p.list_blocks()
    assert result.ok is False

    result = p.get_block_xml("Test")
    assert result.ok is False

    result = p.get_block_interface("Test")
    assert result.ok is False

    result = p.compile_project()
    assert result.ok is False

    result = p.list_devices()
    assert result.ok is False

    result = p.apply_patch({})
    assert result.ok is False
