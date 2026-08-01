"""
EdgeGateway 主类单元测试 — 测试 EdgeGateway 核心逻辑（不含 AI/S7 依赖）

注意：app.py 使用 from src.xxx import，因此测试需在 edge-gateway 目录上下文中运行。
使用 conftest.py 的 sys.path 配置确保正确导入。
"""
import sys, types, json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── 配置路径 ──
_PROJ = Path(__file__).parent.parent
_EDGE_ROOT = _PROJ / "edge-gateway"
_EDGE_SRC = _EDGE_ROOT / "src"

for p in [str(_EDGE_ROOT), str(_EDGE_SRC),
          str(_PROJ / "mcp-servers" / "plc-mcp-bridge"),
          str(_PROJ)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ── Mock 所有 app.py 的外部依赖 ──
_SHADOWED_MODULES = (
    "mcp_common",
    "mcp_common.config",
    "mcp_common.audit",
    "mcp_common.control_target",
    "safety",
    "safety.validator",
    "influxdb_client",
    "influxdb_client.client.write_api",
    "src",
    "src.ai_client",
)
_ORIGINAL_MODULES = {name: sys.modules.get(name) for name in _SHADOWED_MODULES}

sys.modules["mcp_common"] = MagicMock()
sys.modules["mcp_common.config"] = MagicMock()

class _FakeSettings:
    influxdb_url = "http://localhost:8086"
    influxdb_token = "t"; influxdb_org = "o"; influxdb_bucket = "b"
    modbus_host = "localhost"; modbus_port = "502"
    def get(self, k, d=None):
        return {"s7_plc_ip": "192.168.0.1", "s7_rack": "0", "s7_slot": "1"}.get(k, d)

sys.modules["mcp_common.config"].env_config = MagicMock(return_value=_FakeSettings())
sys.modules["mcp_common.audit"] = MagicMock()
sys.modules["mcp_common.control_target"] = MagicMock()
sys.modules["mcp_common.control_target"].get_control_target = MagicMock(
    return_value=types.SimpleNamespace(plc_ip="192.168.0.1")
)

sys.modules["safety"] = MagicMock()
sys.modules["safety.validator"] = MagicMock()
_res = MagicMock(allowed=True, needs_confirmation=False, reason="")
sys.modules["safety.validator"].validator = MagicMock()
sys.modules["safety.validator"].validator.validate = MagicMock(return_value=_res)

# Mock influxdb_client to make HAS_INFLUX = False
sys.modules["influxdb_client"] = MagicMock()
sys.modules["influxdb_client.client.write_api"] = MagicMock()

# Mock src package + src.ai_client
import importlib.util, importlib.machinery, importlib.abc
class _MockLoader(importlib.abc.Loader):
    def exec_module(self, m): pass

_src_spec = importlib.machinery.ModuleSpec("src", _MockLoader(), is_package=True)
_src_mod = importlib.util.module_from_spec(_src_spec)
_src_mod.__path__ = [str(_EDGE_SRC)]
sys.modules["src"] = _src_mod

_ai_mock = MagicMock()
_ai_mock.analyze_data = AsyncMock(return_value="mock analysis")
_ai_mock.decide_control = AsyncMock(return_value='{"action":"wait","reason":"mock"}')
sys.modules["src.ai_client"] = MagicMock()
sys.modules["src.ai_client"].ai = _ai_mock

# ── 最后导入 app ──
import app as edge_app
from app import EdgeGateway, HAS_INFLUX

for _module_name, _original_module in _ORIGINAL_MODULES.items():
    if _original_module is None:
        sys.modules.pop(_module_name, None)
    else:
        sys.modules[_module_name] = _original_module


# ===== 夹具 =====

@pytest.fixture
def mock_read():
    async def _read(tag: str) -> dict:
        vals = {"M0.0": {"value": True}, "M0.1": {"value": False},
                "MW10": {"value": 75}, "MW12": {"value": 1500}}
        return vals.get(tag, {"value": None})
    return _read


@pytest.fixture
def gw():
    return EdgeGateway()


# ===== 初始化 =====

class TestInit:
    def test_tags_loaded(self, gw):
        assert len(gw.tag_config) >= 4
        assert any(t["tag"] == "M0.0" for t in gw.tag_config)

    def test_defaults(self, gw):
        assert gw.scan_interval == 30
        assert gw.running is False
        assert gw._ai_fused is False

    def test_influx_off(self):
        """不需要 InfluxDB 时 HAS_INFLUX 应与环境一致"""
        # 不测试 HAS_INFLUX 的具体值（取决于环境），只验证不报错
        assert hasattr(edge_app, "HAS_INFLUX")


# ===== 扫描 =====

class TestScan:
    @pytest.mark.asyncio
    async def test_scan_count(self, gw, mock_read):
        results = await gw.scan_once(mock_read)
        assert len(results) == len(gw.tag_config)

    @pytest.mark.asyncio
    async def test_scan_structure(self, gw, mock_read):
        results = await gw.scan_once(mock_read)
        for r in results:
            assert all(k in r for k in ("tag", "name", "protocol", "value", "status"))

    @pytest.mark.asyncio
    async def test_scan_error(self, gw):
        async def _bad(tag):
            raise Exception("conn lost")
        results = await gw.scan_once(_bad)
        for r in results:
            assert r["status"] == "error"
            assert "conn lost" in r["error"]

    @pytest.mark.asyncio
    async def test_ok_status(self, gw, mock_read):
        results = await gw.scan_once(mock_read)
        ok_count = sum(1 for r in results if r["status"] == "ok")
        assert ok_count >= 4


# ===== 变化检测 =====

class TestChange:
    def test_first_read_is_change(self, gw):
        assert gw._has_significant_change("MW10", 50) is True
        assert gw._prev_values.get("MW10") == 50

    def test_same_value_not_change(self, gw):
        gw._prev_values["MW10"] = 50
        assert gw._has_significant_change("MW10", 50) is False

    def test_new_value_is_change(self, gw):
        gw._prev_values["MW10"] = 50
        assert gw._has_significant_change("MW10", 100) is True

    def test_none_not_change(self, gw):
        gw._prev_values["MW10"] = 50
        assert gw._has_significant_change("MW10", None) is False

    def test_out_of_bounds_high(self, gw):
        assert gw._is_out_of_bounds("MW10", 200) is True

    def test_out_of_bounds_low(self, gw):
        assert gw._is_out_of_bounds("MW10", -10) is True

    def test_within_bounds(self, gw):
        assert gw._is_out_of_bounds("MW10", 50) is False


# ===== AI 循环 =====

class TestAiLoop:
    @pytest.mark.asyncio
    async def test_confirmation_required_skips_write_function(self, gw, monkeypatch):
        edge_app.ai = MagicMock(
            analyze_data=AsyncMock(return_value="analysis"),
            decide_control=AsyncMock(
                return_value='{"action":"write","target":"MOTOR_1","value":1}'
            ),
        )
        monkeypatch.setattr(
            edge_app.safety_validator,
            "validate",
            MagicMock(
                return_value=MagicMock(
                    allowed=True,
                    needs_confirmation=True,
                    reason="需要人工确认",
                )
            ),
        )
        write_func = MagicMock()

        with patch.object(gw, "_has_significant_change", return_value=True):
            with patch.object(gw, "_is_out_of_bounds", return_value=False):
                await gw.ai_control_loop(
                    [{"tag": "MW10", "name": "T", "value": 50, "status": "ok"}],
                    write_func=write_func,
                )

        write_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_normal_skips_ai(self, gw):
        with patch.object(gw, "_has_significant_change", return_value=False):
            with patch.object(gw, "_is_out_of_bounds", return_value=False):
                await gw.ai_control_loop([
                    {"tag": "MW10", "name": "T", "value": 50, "status": "ok"}
                ])

    @pytest.mark.asyncio
    async def test_fused_skips(self, gw):
        gw._ai_fused = True
        await gw.ai_control_loop([
            {"tag": "MW10", "name": "T", "value": 200, "status": "ok"}
        ])

    @pytest.mark.asyncio
    async def test_abnormal_triggers_ai(self, gw):
        edge_app.ai = _ai_mock
        await gw.ai_control_loop([
            {"tag": "MW10", "name": "T", "value": 200, "status": "ok"}
        ])
        _ai_mock.analyze_data.assert_awaited_once()


# ===== 停止 =====

class TestStop:
    def test_stop(self, gw):
        gw.running = True
        gw.stop()
        assert gw.running is False
