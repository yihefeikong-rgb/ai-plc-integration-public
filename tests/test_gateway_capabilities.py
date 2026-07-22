"""Gateway 能力声明必须与 FastMCP 实际入口一致。"""
from __future__ import annotations

from plc_gateway.bootstrap import GatewayContext
from plc_gateway.config import GatewayConfig


class _Provider:
    available = True


class _Routing:
    def get_read_provider(self):
        return _Provider()


def test_capabilities_only_declare_exposed_read_only_tools():
    context = GatewayContext(GatewayConfig())
    context.routing = _Routing()

    capabilities = context.list_capabilities()

    assert capabilities["declared_count"] == 9
    assert "tia.block.create" not in capabilities["exposed"]
    assert "tia.project.compile" not in capabilities["exposed"]
    assert capabilities["unavailable"] == {
        "tia.block.get_xml": "TiaWorker XML 导出协议尚未验证"
    }
    assert set(capabilities["available"]).issubset(capabilities["exposed"])
