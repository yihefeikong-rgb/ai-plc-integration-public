"""
S7 协议适配器 — 通过 python-snap7 读写西门子 PLC（PLCSIM / 真机）

可作为独立模块被 EdgeGateway import，也可通过 tools_s7.py 注册为 MCP 工具。

用法:
    from s7_adapter import S7Adapter

    adapter = S7Adapter()
    adapter.connect()
    val = adapter.read_merker(0, 0)       # M0.0 bool
    val = adapter.read_byte(0, 0)         # MB0 int
    val = adapter.read_float(0, 0)        # MD0 float
    adapter.write_byte(0, 0, 42)
    adapter.disconnect()
"""
import logging
import math
import re
import sys
from pathlib import Path
from typing import Optional, Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from mcp_common.control_target import TargetConfigurationError, get_control_target, require_control_ip

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
        self._connection_id = ""

    def connect(self, ip: str = "", rack: int = 0, slot: int = 1) -> str:
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

        try:
            target = require_control_ip(ip or get_control_target().plc_ip)
        except TargetConfigurationError as exc:
            return f"🚫 连接被拒绝: {exc}"
        ip = target.plc_ip

        if self._connected:
            return f"⚠ 已连接到 {ip}，请先断开"

        try:
            self._client = snap7.client.Client()
            self._client.connect(ip, rack, slot)
            self._connected = True
            self._connection_id = f"s7:{ip}:{rack}:{slot}"
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
        self._connection_id = ""
        return "✅ 已断开连接"

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    @property
    def device_id(self) -> str:
        """当前连接的唯一目标身份；未连接时为空。"""
        return self._connection_id if self.is_connected else ""

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
        value = self.parse_write_value(f"M{byte}.{bit}", value)
        self._check_connected()
        data = self._client.mb_read(byte, 1)
        util.set_bool(data, 0, bit, value)
        self._client.mb_write(byte, 1, data)
        return f"✅ M{byte}.{bit} = {value}"

    def write_byte(self, db_number: int, start: int, value: int) -> str:
        """写入 DB 区字节"""
        value = self.parse_write_value(f"DB{db_number}.MB{start}", value)
        self._check_connected()
        data = bytearray([value & 0xFF])
        self._client.db_write(db_number, start, data)
        return f"✅ DB{db_number}.{start} = {value}"

    def write_int(self, db_number: int, start: int, value: int) -> str:
        """写入 DB 区 int（2 字节）"""
        value = self.parse_write_value(f"DB{db_number}.MW{start}", value)
        self._check_connected()
        data = bytearray(2)
        util.set_int(data, 0, value)
        self._client.db_write(db_number, start, data)
        return f"✅ DB{db_number}.{start} = {value} (int)"

    def write_real(self, db_number: int, start: int, value: float) -> str:
        """写入 DB 区 real（4 字节）"""
        value = self.parse_write_value(f"DB{db_number}.MD{start}", value)
        self._check_connected()
        data = bytearray(4)
        util.set_real(data, 0, value)
        self._client.db_write(db_number, start, data)
        return f"✅ DB{db_number}.{start} = {value} (real)"

    def write_mw(self, start: int, value: int) -> str:
        """写入 Merker 字 MW（2 字节，M 区）"""
        value = self.parse_write_value(f"MW{start}", value)
        self._check_connected()
        data = bytearray(2)
        util.set_int(data, 0, value)
        self._client.mb_write(start, 2, data)
        return f"✅ MW{start} = {value}"

    def write_md(self, start: int, value: float) -> str:
        """写入 Merker 双字 MD（4 字节，M 区）"""
        value = self.parse_write_value(f"MD{start}", value)
        self._check_connected()
        data = bytearray(4)
        util.set_real(data, 0, value)
        self._client.mb_write(start, 4, data)
        return f"✅ MD{start} = {value}"

    # ── 高级读写（按地址字符串解析） ──

    @staticmethod
    def canonicalize_address(address: str) -> str:
        """规范化并校验地址文本，供安全映射和审计使用。"""
        if not isinstance(address, str):
            raise ValueError("S7 地址必须是字符串")
        normalized = "".join(address.upper().split())
        if not normalized:
            raise ValueError("S7 地址不能为空")
        return normalized

    @staticmethod
    def _parse_non_negative_int(value: str, field: str) -> int:
        if not value.isdigit():
            raise ValueError(f"{field} 必须是非负整数")
        return int(value)

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
        addr = S7Adapter.canonicalize_address(address)
        if addr.startswith("DB"):
            # DB1.MW10 或 DB1.MD20
            rest = addr[2:]  # "1.MW10"
            parts = rest.split(".", 1)
            if len(parts) != 2:
                raise ValueError(f"不支持的地址格式: {address}")
            db_num = S7Adapter._parse_non_negative_int(parts[0], "DB 编号")
            inner = parts[1]
            return S7Adapter._parse_inner(inner, db_num)
        else:
            return S7Adapter._parse_inner(addr, 0)

    @staticmethod
    def _parse_inner(addr: str, db_num: int) -> tuple:
        if addr.startswith("M"):
            rest = addr[1:]  # "0.0", "W10", "D20"
            if "." in rest:
                parts = rest.split(".")
                if len(parts) != 2:
                    raise ValueError(f"不支持的地址格式: {addr}")
                b, bit = parts
                byte = S7Adapter._parse_non_negative_int(b, "字节地址")
                bit_number = S7Adapter._parse_non_negative_int(bit, "位地址")
                if bit_number > 7:
                    raise ValueError(f"位地址必须在 0-7 之间: {addr}")
                return ("M", db_num, byte, bit_number)
            elif rest.startswith("W"):
                return ("MW", db_num, S7Adapter._parse_non_negative_int(rest[1:], "字地址"), 2)
            elif rest.startswith("D"):
                return ("MD", db_num, S7Adapter._parse_non_negative_int(rest[1:], "双字地址"), 4)
            else:
                raw_byte = rest[1:] if rest.startswith("B") else rest
                return ("MB", db_num, S7Adapter._parse_non_negative_int(raw_byte, "字节地址"), 1)
        return ("UNKNOWN", 0, 0, 0)

    @staticmethod
    def address_value_type(address: str) -> str:
        """返回地址的唯一可写入值类型。"""
        typ, _, _, _ = S7Adapter._parse_addr(address)
        value_types = {"M": "bool", "MB": "uint8", "MW": "int16", "MD": "float32"}
        try:
            return value_types[typ]
        except KeyError as exc:
            raise ValueError(f"不支持的地址格式: {address}") from exc

    @staticmethod
    def _parse_integer(value: Any, *, minimum: int, maximum: int, type_name: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{type_name} 不接受布尔值")
        if isinstance(value, int):
            parsed = value
        elif isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value.strip()):
            parsed = int(value.strip())
        else:
            raise ValueError(f"{type_name} 必须是十进制整数")
        if not minimum <= parsed <= maximum:
            raise ValueError(f"{type_name} 超出范围: {parsed}（允许 {minimum}..{maximum}）")
        return parsed

    @staticmethod
    def _parse_float(value: Any) -> float:
        if isinstance(value, bool):
            raise ValueError("float32 不接受布尔值")
        if isinstance(value, (int, float)):
            parsed = float(value)
        elif isinstance(value, str) and value.strip():
            try:
                parsed = float(value.strip())
            except ValueError as exc:
                raise ValueError("float32 必须是十进制浮点数") from exc
        else:
            raise ValueError("float32 必须是十进制浮点数")
        if not math.isfinite(parsed):
            raise ValueError("float32 必须是有限数值")
        if abs(parsed) > 3.4028235e38:
            raise ValueError("float32 超出范围")
        return parsed

    @classmethod
    def parse_write_value(cls, address: str, value: Any) -> bool | int | float:
        """按 S7 物理地址严格解析写入值，拒绝隐式类型转换。"""
        value_type = cls.address_value_type(address)
        if value_type == "bool":
            if type(value) is bool:
                return value
            if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
                return value.strip().lower() == "true"
            raise ValueError("bool 仅接受 true 或 false")
        if value_type == "uint8":
            return cls._parse_integer(value, minimum=0, maximum=255, type_name="uint8")
        if value_type == "int16":
            return cls._parse_integer(value, minimum=-32768, maximum=32767, type_name="int16")
        return cls._parse_float(value)

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
        address = self.canonicalize_address(address)
        typ, db, start, extra = self._parse_addr(address)
        if typ == "UNKNOWN":
            return f"❌ 不支持的地址格式: {address}"
        typed_value = self.parse_write_value(address, value)
        if typ == "M":
            return self.write_merker(start, extra, typed_value)
        elif typ == "MB":
            if db:
                return self.write_byte(db, start, typed_value)
            return self.write_byte(0, start, typed_value)
        elif typ == "MW":
            if db:
                return self.write_int(db, start, typed_value)
            return self.write_mw(start, typed_value)
        elif typ == "MD":
            if db:
                return self.write_real(db, start, typed_value)
            return self.write_md(start, typed_value)
        return f"❌ 不支持的地址格式: {address}"


# 全局单例
adapter = S7Adapter()
