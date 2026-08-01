"""
PLCSIM Advanced 集成验证测试。

通过 python-snap7 v3 直连 PLCSIM Advanced 实例进行 S7 协议读写验证。
仅在真实 PLCSIM 实例可用时运行，否则自动 skip。

运行方式:
    pytest orchestrator/tests/test_plcsim_integration.py -v -m integration
    pytest orchestrator/tests/test_plcsim_integration.py -v -m "integration and not skip"
"""
import sys
from pathlib import Path

import pytest

from mcp_common.control_target import (
    TargetConfigurationError,
    get_control_target,
    require_control_ip,
)
from config_loader import cfg as _tia_cfg

# 添加 bridge 源码路径以便 s7_adapter import
BRIDGE_ROOT = Path(__file__).parent.parent.parent / "mcp-servers" / "plc-mcp-bridge"
if str(BRIDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(BRIDGE_ROOT))

pytestmark = [pytest.mark.integration]

CONTROL_TARGET = get_control_target()

PLCSIM_IP = CONTROL_TARGET.plc_ip
PLCSIM_RACK = int(_tia_cfg.simulation.advanced.rack)
PLCSIM_SLOT = int(_tia_cfg.simulation.advanced.slot)
PLCSIM_PORT = int(_tia_cfg.simulation.advanced.port)


def _try_connect_plcsim():
    """尝试连接 PLCSIM，返回 (client, error_msg)。

    成功: (snap7.Client, None)
    失败: (None, error_msg)
    """
    try:
        import snap7
    except ImportError as exc:
        return None, f"snap7 未安装: {exc}"

    client = snap7.client.Client()
    try:
        client.connect(PLCSIM_IP, PLCSIM_RACK, PLCSIM_SLOT, PLCSIM_PORT)
        return client, None
    except Exception as exc:
        try:
            client.destroy()
        except Exception:
            pass
        return None, f"{type(exc).__name__}: {exc}"


def _disconnect_plcsim(client):
    """安全断开并销毁 client。"""
    if client is None:
        return
    try:
        client.disconnect()
    except Exception:
        pass
    try:
        client.destroy()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def plcsim_client():
    """模块级 fixture：创建并连接 PLCSIM client，所有测试共用。"""
    client, error = _try_connect_plcsim()
    if client is None:
        pytest.skip(f"PLCSIM 不可用: {error}")
    yield client
    _disconnect_plcsim(client)


# ---------------------------------------------------------------------------
# 连接生命周期测试
# ---------------------------------------------------------------------------


class TestConnectionLifecycle:
    """连接/断开生命周期"""

    def test_connect(self, plcsim_client):
        """验证连接成功返回有效的 client 对象"""
        assert plcsim_client is not None
        # 验证 client 处于已连接状态（snap7 v3 确认有 get_connected）
        connected = plcsim_client.get_connected()
        assert connected is True

    def test_target_drift_rejected_before_connect(self):
        """非唯一控制目标必须在任何网络连接前被拒绝。"""
        with pytest.raises(TargetConfigurationError):
            require_control_ip("203.0.113.10")

    def test_disconnect_and_reconnect(self):
        """断开后可以重新连接"""
        client, error = _try_connect_plcsim()
        if client is None:
            pytest.skip(f"PLCSIM 不可用: {error}")

        # 断开
        _disconnect_plcsim(client)

        # 重新连接
        client2, error2 = _try_connect_plcsim()
        if client2 is None:
            pytest.fail(f"重新连接失败: {error2}")

        assert client2 is not None
        _disconnect_plcsim(client2)


# ---------------------------------------------------------------------------
# Merker (M) 区读写测试
# ---------------------------------------------------------------------------


class TestMerkerReadWrite:
    """M 区位/字节/字/双字读写验证"""

    def test_mb_read(self, plcsim_client):
        """MB0 字节读取"""
        data = plcsim_client.mb_read(0, 1)
        assert data is not None
        assert len(data) == 1

    def test_mw_read(self, plcsim_client):
        """MW0 字读取（2 字节）"""
        data = plcsim_client.mb_read(0, 2)
        assert data is not None
        assert len(data) == 2

    def test_md_read(self, plcsim_client):
        """MD0 双字读取（4 字节）"""
        data = plcsim_client.mb_read(0, 4)
        assert data is not None
        assert len(data) == 4

    def test_m_bit_read(self, plcsim_client):
        """M0.0 位读取（使用 snap7 util）"""
        from snap7 import util as snap7_util
        data = plcsim_client.mb_read(0, 1)
        bit0 = snap7_util.get_bool(data, 0, 0)
        assert bit0 in (True, False)

    def test_mb_write_then_read(self, plcsim_client):
        """写入 MB0=42，回读验证"""
        original = plcsim_client.mb_read(0, 1)
        try:
            plcsim_client.mb_write(0, 1, bytearray([42]))
            data = plcsim_client.mb_read(0, 1)
            assert data[0] == 42
        finally:
            plcsim_client.mb_write(0, 1, original)

    def test_mw_write_then_read(self, plcsim_client):
        """写入 MW0=12345，回读验证"""
        from snap7 import util as snap7_util
        original = plcsim_client.mb_read(0, 2)
        data = bytearray(2)
        snap7_util.set_int(data, 0, 12345)
        try:
            plcsim_client.mb_write(0, 2, data)
            readback = plcsim_client.mb_read(0, 2)
            value = snap7_util.get_int(readback, 0)
            assert value == 12345
        finally:
            plcsim_client.mb_write(0, 2, original)

    def test_md_write_then_read(self, plcsim_client):
        """写入 MD0=3.14，回读验证"""
        from snap7 import util as snap7_util
        original = plcsim_client.mb_read(0, 4)
        data = bytearray(4)
        snap7_util.set_real(data, 0, 3.14)
        try:
            plcsim_client.mb_write(0, 4, data)
            readback = plcsim_client.mb_read(0, 4)
            value = snap7_util.get_real(readback, 0)
            assert abs(value - 3.14) < 0.01
        finally:
            plcsim_client.mb_write(0, 4, original)

    def test_m_bit_write_then_read(self, plcsim_client):
        """写入 M0.0=True，回读验证"""
        from snap7 import util as snap7_util
        # 先读当前字节
        original = plcsim_client.mb_read(0, 1)
        data = bytearray(original)
        snap7_util.set_bool(data, 0, 0, True)
        try:
            plcsim_client.mb_write(0, 1, data)
            readback = plcsim_client.mb_read(0, 1)
            bit0 = snap7_util.get_bool(readback, 0, 0)
            assert bit0 is True
        finally:
            plcsim_client.mb_write(0, 1, original)


# ---------------------------------------------------------------------------
# DB 区读写测试
# ---------------------------------------------------------------------------


class TestDbReadWrite:
    """DB 区读写验证

    注意: PLCSIM 必须加载了包含目标 DB 块的项目才能读写 DB。
    如果 DB1 不存在，测试会被 skip。
    """

    def test_db_read_available(self, plcsim_client):
        """尝试读取 DB1 byte 0，如果 DB1 存在则读，否则 skip"""
        try:
            data = plcsim_client.db_read(1, 0, 1)
        except Exception as e:
            msg = str(e).lower()
            if "not found" in msg or "doesn't exist" in msg or "error" in msg or "invalid" in msg:
                pytest.skip(f"DB1 不可用（PLC 可能未加载项目）: {e}")
            raise
        assert data is not None
        assert len(data) == 1

    def test_db_write_then_read(self, plcsim_client):
        """写入 DB1.byte0=99，回读验证"""
        try:
            original = plcsim_client.db_read(1, 0, 1)
        except Exception as e:
            msg = str(e).lower()
            if any(kw in msg for kw in ("not found", "doesn't exist", "error", "invalid")):
                pytest.skip(f"DB1 不可用（PLC 可能未加载项目）: {e}")
            raise

        try:
            plcsim_client.db_write(1, 0, bytearray([99]))
            readback = plcsim_client.db_read(1, 0, 1)
            assert readback[0] == 99
        finally:
            plcsim_client.db_write(1, 0, original)


# ---------------------------------------------------------------------------
# S7Adapter 包装测试
# ---------------------------------------------------------------------------


class TestS7AdapterWithRealPLC:
    """使用 s7_adapter.py 的 S7Adapter 封装连接真实 PLCSIM"""

    @pytest.fixture
    def adapter(self, plcsim_client):
        from s7_adapter import S7Adapter
        a = S7Adapter()
        a._client = plcsim_client
        a._connected = True
        return a

    def test_adapter_is_connected(self, adapter):
        assert adapter.is_connected is True

    def test_adapter_read_merker(self, adapter):
        val = adapter.read_merker(0, 0)
        assert val in (True, False)

    def test_adapter_read_mw(self, adapter):
        val = adapter.read_mw(0)
        assert isinstance(val, int)

    def test_adapter_write_then_read_mw(self, adapter):
        original = adapter.read_mw(10)
        try:
            result = adapter.write_mw(10, 256)
            assert "✅" in result
            val = adapter.read_mw(10)
            assert val == 256
        finally:
            adapter.write_mw(10, original)

    def test_adapter_read_address_M0_0(self, adapter):
        val = adapter.read_address("M0.0")
        assert val in (True, False)

    def test_adapter_read_address_MW0(self, adapter):
        val = adapter.read_address("MW0")
        assert isinstance(val, int)

    def test_adapter_write_address_MD4(self, adapter):
        original = adapter.read_address("MD4")
        try:
            result = adapter.write_address("MD4", 2.718)
            assert "✅" in result
            val = adapter.read_address("MD4")
            assert abs(val - 2.718) < 0.1
        finally:
            adapter.write_address("MD4", original)

    def test_adapter_disconnect_and_not_connected(self, adapter):
        adapter.disconnect()
        assert adapter.is_connected is False

        with pytest.raises(ConnectionError):
            adapter.read_address("MW0")
