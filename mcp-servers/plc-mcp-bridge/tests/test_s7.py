"""S7 适配器单测 — 地址解析 + mock 模式测试"""
from unittest.mock import patch, MagicMock, PropertyMock
import pytest


class TestS7AddressParsing:
    """地址解析是纯字符串逻辑，不依赖 snap7"""

    def _parse(self, addr):
        from s7_adapter import S7Adapter
        return S7Adapter._parse_addr(addr)

    def _parse_inner(self, addr, db=0):
        from s7_adapter import S7Adapter
        return S7Adapter._parse_inner(addr, db)

    @pytest.mark.parametrize("addr,expected", [
        ("M0.0", ("M", 0, 0, 0)),
        ("M1.5", ("M", 0, 1, 5)),
        ("M15.7", ("M", 0, 15, 7)),
        ("MB10", ("MB", 0, 10, 1)),
        ("MW10", ("MW", 0, 10, 2)),
        ("MD20", ("MD", 0, 20, 4)),
        ("DB1.MW10", ("MW", 1, 10, 2)),
        ("DB1.MD20", ("MD", 1, 20, 4)),
        ("DB100.MW0", ("MW", 100, 0, 2)),
    ])
    def test_parse_addr(self, addr, expected):
        assert self._parse(addr) == expected

    @pytest.mark.parametrize("addr,expected", [
        ("M0.0", ("M", 0, 0, 0)),
        ("MB0", ("MB", 0, 0, 1)),
        ("MW10", ("MW", 0, 10, 2)),
    ])
    def test_parse_inner(self, addr, expected):
        assert self._parse_inner(addr) == expected

    def test_parse_unknown(self):
        assert self._parse("X0")[0] == "UNKNOWN"

    def test_parse_lowercase(self):
        assert self._parse("mw10") == ("MW", 0, 10, 2)

    def test_db1_mw_case(self):
        assert self._parse("db1.mw10") == ("MW", 1, 10, 2)

    def test_db_number_multidigit(self):
        assert self._parse("DB123.MW456") == ("MW", 123, 456, 2)


class TestS7AdapterSnap7NotAvailable:
    """snap7 未安装时的行为"""

    def test_connect_returns_error(self):
        with patch('s7_adapter.SNAP7_AVAILABLE', False):
            from s7_adapter import S7Adapter
            a = S7Adapter()
            result = a.connect("192.168.0.1")
            assert "未安装" in result

    def test_disconnect_when_not_connected(self):
        from s7_adapter import S7Adapter
        a = S7Adapter()
        assert "未连接" in a.disconnect()


class TestS7AdapterWithMockClient:
    """mock snap7 client 测试读写逻辑"""

    @pytest.fixture
    def adapter(self):
        from s7_adapter import S7Adapter
        a = S7Adapter()
        a._client = MagicMock()
        a._connected = True
        return a

    def test_read_merker(self, adapter):
        adapter._client.mb_read.return_value = bytearray([0b00000001])
        from snap7 import util as _  # 确保 import 可用
        val = adapter.read_merker(0, 0)
        adapter._client.mb_read.assert_called_with(0, 1)

    def test_read_byte(self, adapter):
        adapter._client.db_read.return_value = bytearray([42])
        assert adapter.read_byte(1, 0) == 42
        adapter._client.db_read.assert_called_with(1, 0, 1)

    def test_read_mw_uses_mb_read(self, adapter):
        """MW10 走 mb_read 不走 db_read"""
        adapter._client.mb_read.return_value = bytearray([0, 100])
        val = adapter.read_address("MW10")
        adapter._client.mb_read.assert_called_with(10, 2)

    def test_read_db_mw_uses_db_read(self, adapter):
        """DB1.MW10 走 db_read"""
        adapter._client.db_read.return_value = bytearray([0, 200])
        adapter.read_address("DB1.MW10")
        adapter._client.db_read.assert_called_with(1, 10, 2)

    def test_write_mw_uses_mb_write(self, adapter):
        adapter._client.mb_write.return_value = None
        r = adapter.write_address("MW10", 500)
        assert "MW10" in r
        adapter._client.mb_write.assert_called_once()

    def test_write_db_mw_uses_db_write(self, adapter):
        adapter._client.db_write.return_value = None
        r = adapter.write_address("DB1.MW10", 500)
        assert "DB1" in r
        adapter._client.db_write.assert_called_once()

    def test_write_md_uses_mb_write(self, adapter):
        adapter._client.mb_write.return_value = None
        r = adapter.write_address("MD20", 1.5)
        assert "MD20" in r

    def test_write_merker_bit(self, adapter):
        adapter._client.mb_read.return_value = bytearray([0])
        adapter._client.mb_write.return_value = None
        r = adapter.write_address("M0.0", True)
        assert "M0.0" in r

    def test_write_unknown_address(self, adapter):
        r = adapter.write_address("X0", 1)
        assert "不支持" in r

    def test_read_checks_connection(self):
        from s7_adapter import S7Adapter
        a = S7Adapter()  # 未连接
        with pytest.raises(ConnectionError):
            a.read_address("MW10")

    def test_write_checks_connection(self):
        from s7_adapter import S7Adapter
        a = S7Adapter()  # 未连接
        with pytest.raises(ConnectionError):
            a.write_address("MW10", 100)

    def test_connect_without_client(self):
        """is_connected 返回 False 当 client 为 None"""
        from s7_adapter import S7Adapter
        a = S7Adapter()
        assert a.is_connected is False
