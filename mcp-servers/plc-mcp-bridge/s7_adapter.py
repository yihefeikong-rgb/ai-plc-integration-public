"""
S7 协议适配器 — 通过 python-snap7 读写西门子 PLC（PLCSIM / 真机）

可作为独立模块被 EdgeGateway import，也可通过 tools_s7.py 注册为 MCP 工具。

用法:
    from s7_adapter import S7Adapter

    adapter = S7Adapter()
    adapter.connect("192.168.0.110", 0, 1)
    val = adapter.read_merker(0, 0)       # M0.0 bool
    val = adapter.read_byte(0, 0)         # MB0 int
    val = adapter.read_float(0, 0)        # MD0 float
    adapter.write_byte(0, 0, 42)
    adapter.disconnect()
"""
import logging
from typing import Optional, Any

logger = logging.getLogger("s7_adapter")

try:
    import snap7
    from snap7 import util
    SNAP7_AVAILABLE = True
except ImportError:
    SNAP7_AVAILABLE = False


class S7Adapter:
    """S7 协议适配器，封装 snap7 客户端"""

    def __init__(self):
        self._client = None
        self._connected = False

    def connect(self, ip: str = "192.168.0.110", rack: int = 0, slot: int = 1) -> str:
        """连接到 PLC

        Args:
            ip: PLC IP 地址
            rack: 机架号（默认 0）
            slot: 插槽号（默认 1）

        Returns:
            连接结果消息
        """
        if not SNAP7_AVAILABLE:
            return "❌ python-snap7 未安装: pip install python-snap7"

        if self._connected:
            return f"⚠ 已连接到 {ip}，请先断开"

        try:
            self._client = snap7.client.Client()
            self._client.connect(ip, rack, slot)
            self._connected = True
            return f"✅ 已连接到 S7 PLC ({ip}, Rack={rack}, Slot={slot})"
        except Exception as e:
            self._client = None
            return f"❌ 连接失败: {e}"

    def disconnect(self) -> str:
        """断开 PLC 连接"""
        if not self._connected or self._client is None:
            return "⚠ 未连接"
        try:
            self._client.disconnect()
            self._client.destroy()
        except Exception:
            pass
        self._client = None
        self._connected = False
        return "✅ 已断开连接"

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    def _check_connected(self):
        if not self.is_connected:
            raise ConnectionError("未连接 PLC，请先调用 connect()")

    # ── 读取 ──

    def read_merker(self, byte: int, bit: int) -> bool:
        """读取 M 区位（bool）

        Args:
            byte: 字节地址
            bit: 位地址 (0-7)
        """
        self._check_connected()
        data = self._client.mb_read(byte, 1)
        return util.get_bool(data, 0, bit)

    def read_byte(self, db_number: int, start: int, size: int = 1) -> int:
        """读取 DB 区字节

        Args:
            db_number: DB 块编号
            start: 起始地址
            size: 字节数（默认 1）
        """
        self._check_connected()
        data = self._client.db_read(db_number, start, size)
        return data[0]

    def read_int(self, db_number: int, start: int) -> int:
        """读取 DB 区 int（2 字节）"""
        self._check_connected()
        data = self._client.db_read(db_number, start, 2)
        return util.get_int(data, 0)

    def read_real(self, db_number: int, start: int) -> float:
        """读取 DB 区 real/float（4 字节）"""
        self._check_connected()
        data = self._client.db_read(db_number, start, 4)
        return util.get_real(data, 0)

    def read_dword(self, db_number: int, start: int) -> int:
        """读取 DB 区 dword（4 字节）"""
        self._check_connected()
        data = self._client.db_read(db_number, start, 4)
        return util.get_dword(data, 0)

    def read_mw(self, start: int) -> int:
        """读取 Merker 字 MW（2 字节，M 区）"""
        self._check_connected()
        data = self._client.mb_read(start, 2)
        return util.get_int(data, 0)

    def read_md(self, start: int) -> float:
        """读取 Merker 双字 MD（4 字节，M 区）"""
        self._check_connected()
        data = self._client.mb_read(start, 4)
        return util.get_real(data, 0)

    # ── 写入 ──

    def write_merker(self, byte: int, bit: int, value: bool) -> str:
        """写入 M 区位

        Args:
            byte: 字节地址
            bit: 位地址 (0-7)
            value: True/False
        """
        self._check_connected()
        data = self._client.mb_read(byte, 1)
        util.set_bool(data, 0, bit, value)
        self._client.mb_write(byte, 1, data)
        return f"✅ M{byte}.{bit} = {value}"

    def write_byte(self, db_number: int, start: int, value: int) -> str:
        """写入 DB 区字节"""
        self._check_connected()
        data = bytearray([value & 0xFF])
        self._client.db_write(db_number, start, data)
        return f"✅ DB{db_number}.{start} = {value}"

    def write_int(self, db_number: int, start: int, value: int) -> str:
        """写入 DB 区 int（2 字节）"""
        self._check_connected()
        data = bytearray(2)
        util.set_int(data, 0, value)
        self._client.db_write(db_number, start, data)
        return f"✅ DB{db_number}.{start} = {value} (int)"

    def write_real(self, db_number: int, start: int, value: float) -> str:
        """写入 DB 区 real（4 字节）"""
        self._check_connected()
        data = bytearray(4)
        util.set_real(data, 0, value)
        self._client.db_write(db_number, start, data)
        return f"✅ DB{db_number}.{start} = {value} (real)"

    def write_mw(self, start: int, value: int) -> str:
        """写入 Merker 字 MW（2 字节，M 区）"""
        self._check_connected()
        data = bytearray(2)
        util.set_int(data, 0, value)
        self._client.mb_write(start, 2, data)
        return f"✅ MW{start} = {value}"

    def write_md(self, start: int, value: float) -> str:
        """写入 Merker 双字 MD（4 字节，M 区）"""
        self._check_connected()
        data = bytearray(4)
        util.set_real(data, 0, value)
        self._client.mb_write(start, 4, data)
        return f"✅ MD{start} = {value}"

    # ── 高级读写（按地址字符串解析） ──

    @staticmethod
    def _parse_addr(address: str) -> tuple:
        """解析地址字符串，返回 (type, db_num, byte, bit_or_size)

        Args:
            address: 如 "M0.0", "MB0", "MW10", "MD20", "DB1.MW10", "DB1.MD20"

        Returns:
            (type, db_num, start, extra)
            type: "M", "MB" 等
            db_num: DB 块号或 0
            start: 起始字节
            extra: bit 位或字节数
        """
        addr = address.upper().replace(" ", "")
        if addr.startswith("DB"):
            # DB1.MW10 或 DB1.MD20
            rest = addr[2:]  # "1.MW10"
            parts = rest.split(".")
            db_num = int(parts[0])
            inner = ".".join(parts[1:])
            return S7Adapter._parse_inner(inner, db_num)
        else:
            return S7Adapter._parse_inner(addr, 0)

    @staticmethod
    def _parse_inner(addr: str, db_num: int) -> tuple:
        if addr.startswith("M"):
            rest = addr[1:]  # "0.0", "W10", "D20"
            if "." in rest:
                b, bit = rest.split(".")
                return ("M", db_num, int(b), int(bit))
            elif rest.startswith("W"):
                return ("MW", db_num, int(rest[1:]), 2)
            elif rest.startswith("D"):
                return ("MD", db_num, int(rest[1:]), 4)
            else:
                return ("MB", db_num, int(rest.lstrip("B")), 1)
        return ("UNKNOWN", 0, 0, 0)

    def read_address(self, address: str) -> Any:
        """按地址字符串读取

        Args:
            address: "M0.0", "MB0", "MW10", "MD20", "DB1.MW10"

        Returns:
            读取的值
        """
        typ, db, start, extra = self._parse_addr(address)
        if typ == "M":
            return self.read_merker(start, extra)
        elif typ == "MB":
            if db:
                return self.read_byte(db, start)
            return self.read_byte(0, start)
        elif typ == "MW":
            if db:  # DB 块中的字, 如 DB1.MW10
                return self.read_int(db, start)
            return self.read_mw(start)  # Merker 字
        elif typ == "MD":
            if db:  # DB 块中的双字, 如 DB1.MD20
                return self.read_real(db, start)
            return self.read_md(start)  # Merker 双字
        raise ValueError(f"不支持的地址格式: {address}")

    def write_address(self, address: str, value: Any) -> str:
        """按地址字符串写入

        Args:
            address: "M0.0", "MB0", "MW10", "MD20", "DB1.MW10"
            value: 要写入的值

        Returns:
            写入结果消息
        """
        typ, db, start, extra = self._parse_addr(address)
        if typ == "M":
            return self.write_merker(start, extra, bool(value))
        elif typ == "MB":
            if db:
                return self.write_byte(db, start, int(value))
            return self.write_byte(0, start, int(value))
        elif typ == "MW":
            if db:
                return self.write_int(db, start, int(value))
            return self.write_mw(start, int(value))
        elif typ == "MD":
            if db:
                return self.write_real(db, start, float(value))
            return self.write_md(start, float(value))
        return f"❌ 不支持的地址格式: {address}"


# 全局单例
adapter = S7Adapter()
