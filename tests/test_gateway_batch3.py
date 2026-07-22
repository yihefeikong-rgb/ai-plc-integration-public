"""
PLC Gateway — Batch 3 验收测试（从 Gateway 目录运行）

运行方式：
  cd mcp-servers/plc-gateway && python -m pytest ../../tests/test_gateway_batch3.py -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _ensure_gw_path():
    """确保 gateway 目录在 sys.path 中"""
    p = Path(__file__).resolve().parents[2] / "mcp-servers" / "plc-gateway"
    ps = str(p)
    if ps in sys.path:
        sys.path.remove(ps)
    sys.path.insert(0, ps)


_ensure_gw_path()


def test_config_defaults():
    from config import GatewayConfig
    cfg = GatewayConfig()
    assert cfg.tia_version == "V21"
    assert cfg.safety_enabled is True
    assert cfg.tiacommander_enabled is False
    assert cfg.default_read_provider == "tiaworker"


def test_config_from_env():
    os.environ["GATEWAY_TARGET_PROJECT"] = "/test/project"
    os.environ["GATEWAY_TIA_VERSION"] = "V18"
    os.environ["GATEWAY_TIACOMMANDER_ENABLED"] = "1"
    os.environ["GATEWAY_SAFETY_ENABLED"] = "0"
    os.environ["GATEWAY_DEBUG"] = "1"

    from config import GatewayConfig
    cfg = GatewayConfig.from_env()
    assert cfg.target_project == "/test/project"
    assert cfg.tia_version == "V18"
    assert cfg.tiacommander_enabled is True
    assert cfg.safety_enabled is False
    assert cfg.debug is True

    for k in ["GATEWAY_TARGET_PROJECT", "GATEWAY_TIA_VERSION",
              "GATEWAY_TIACOMMANDER_ENABLED", "GATEWAY_SAFETY_ENABLED",
              "GATEWAY_DEBUG"]:
        os.environ.pop(k, None)


def test_config_to_dict():
    from config import GatewayConfig
    cfg = GatewayConfig(target_project="/test")
    d = cfg.to_dict()
    assert d["target_project"] == "/test"
    assert d["tia_version"] == "V21"
    assert "safety_enabled" in d


def test_bootstrap_context():
    from config import GatewayConfig
    from bootstrap import bootstrap_gateway

    cfg = GatewayConfig(safety_enabled=True, debug=True)
    ctx = bootstrap_gateway(cfg)
    assert ctx.gateway_id is not None
    assert len(ctx.gateway_id) == 8
    assert ctx.config is cfg
    assert ctx.registry is not None
    assert ctx.safety is not None
    assert ctx.routing is not None


def test_bootstrap_context_disabled_safety():
    from config import GatewayConfig
    from bootstrap import bootstrap_gateway

    cfg = GatewayConfig(safety_enabled=False, debug=True)
    ctx = bootstrap_gateway(cfg)
    assert ctx.safety is None


def test_bootstrap_registers_tools():
    from config import GatewayConfig
    from bootstrap import bootstrap_gateway

    cfg = GatewayConfig(debug=True)
    ctx = bootstrap_gateway(cfg)
    assert len(ctx.registry) == 34, f"预期 34 个工具，实际 {len(ctx.registry)}"


def test_bootstrap_context_to_dict():
    from config import GatewayConfig
    from bootstrap import bootstrap_gateway

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
    from config import GatewayConfig
    from bootstrap import bootstrap_gateway

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
    from config import GatewayConfig
    from bootstrap import bootstrap_gateway

    cfg = GatewayConfig(debug=True)
    ctx = bootstrap_gateway(cfg)
    caps = ctx.list_capabilities()
    assert "gateway.get_info" in caps
    assert "gateway.list_providers" in caps
    assert "gateway.list_capabilities" in caps
    assert "tia.block.list" in caps
    assert "tia.block.get_xml" in caps
    assert "tia.project.list" in caps
    assert "tia.hardware.list" in caps


def test_server_fastmcp_tools():
    import asyncio
    from server import mcp, get_context

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
    from bootstrap import _UnavailableProvider

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