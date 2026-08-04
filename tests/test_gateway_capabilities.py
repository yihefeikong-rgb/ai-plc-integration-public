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

    # declared_count 必须与 exposed 清单一致，而不是硬编码具体数量
    assert capabilities["declared_count"] == len(capabilities["exposed"])
    assert "tia.block.create" not in capabilities["exposed"]
    assert "tia.project.compile" not in capabilities["exposed"]
    # unavailable 只能引用已声明能力；每个 exposed 能力必须恰好落入
    # available 或 unavailable 之一（无静默缺口）并带非空原因 —— fail-closed
    assert set(capabilities["unavailable"]).issubset(capabilities["exposed"])
    assert set(capabilities["exposed"]) == (
        set(capabilities["available"]) | set(capabilities["unavailable"])
    )
    assert set(capabilities["available"]).isdisjoint(capabilities["unavailable"])
    assert all(capabilities["unavailable"].values())
    assert set(capabilities["available"]).issubset(capabilities["exposed"])
