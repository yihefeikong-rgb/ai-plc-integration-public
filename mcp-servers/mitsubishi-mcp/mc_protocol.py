"""
三菱 MC 协议（MELSEC Communication Protocol）
3E Binary 帧，TCP 传输，支持 FX3U/FX5U/Q/iQ-R 系列

标准 3E Binary 帧结构:
  请求: Subheader(2) + Network(1) + PC(1) + DestIO(2) + DestStation(1)
        + DataLen(2) + Timer(2) + Command(2) + Subcommand(2) + DeviceData
  响应: Subheader(2) + Network(1) + PC(1) + DestIO(2) + DestStation(1)
        + DataLen(2) + EndCode(2) + Data

响应头共 9 字节（Subheader~DataLen），EndCode 在 offset 9。
"""

import struct
import re
from enum import IntEnum

# ── 帧常量 ──
SUBHEADER_REQ = 0x5000       # 请求子头
SUBHEADER_RESP = 0xD000      # 响应子头
NETWORK_NO = 0x00            # 网络号（同网络）
PC_NO = 0xFF                 # PC 号
DEST_IO = 0x03FF             # 目标模块 I/O（CPU）
DEST_STATION = 0x00          # 目标站号

# 帧头长度（Subheader ~ DataLen 共 9 字节）
RESP_HEADER_LEN = 9

# 监视定时器（250ms 单位，0x0010 = 16 × 250ms = 4s）
MONITOR_TIMER = 0x0010

# 设备编号最大可编码值（3E Binary 帧内设备编号为 3 字节，超过即静默截断回绕）
MAX_DEVICE_OFFSET = 0xFFFFFF

# PLC 系列：决定 X/Y 设备编号的进制。
#   "FX" — FX3U/FX5U：X/Y 为八进制编号（X10/Y20 在帧内编码为 0x000008/0x000010）
#   "Q"  — Q/iQ-R：X/Y 为十六进制编号（X10/Y20 在帧内编码为 0x000010/0x000020）
# 默认 FX，与本模块 server.py 声明的支持范围（FX3U/FX5U）一致。Q 系列须在
# 建立连接前调用 set_plc_series("Q")，否则 X/Y 会按错误的进制解释指向错误
# 的物理点（如写 Y20 实际驱动其它输出）。
PLC_SERIES = "FX"

# 命令码
CMD_BATCH_READ = 0x0401
CMD_BATCH_WRITE = 0x1401

# 子命令码（2 字节）
SUBCMD_WORD = 0x0000  # 字访问
SUBCMD_BIT = 0x0001   # 位访问

# 设备代码
DEVICE_CODES = {
    "M": 0x90, "X": 0x9C, "Y": 0x9D, "D": 0xA8,
    "L": 0x92, "B": 0xA0, "W": 0xB4,
    "T": 0xC2, "TN": 0xC4, "C": 0xC5, "CN": 0xC6,
    "S": 0x98, "V": 0x9A, "F": 0x97,
    "Z": 0xCC, "ZR": 0xB0, "R": 0xAF, "SW": 0xB5,
}

# 位访问设备代码（与 is_bit_device 声明的位设备集合一致）
_BIT_DEVICE_CODES = frozenset(
    DEVICE_CODES[dev] for dev in ("M", "X", "Y", "L", "B", "T", "C", "S", "V", "F")
)


class MCFrameError(Exception):
    pass


def set_plc_series(series: str) -> None:
    """设置 PLC 系列，决定 X/Y 设备编号的进制（'FX'=八进制, 'Q'=十六进制）。

    必须在建立连接前调用；未调用时默认 FX（与 server.py 声明一致）。
    非法系列直接拒绝，避免在未知进制下解析 X/Y 地址。
    """
    global PLC_SERIES
    series = series.upper()
    if series not in ("FX", "Q"):
        raise MCFrameError(f"不支持的 PLC 系列: {series} (支持 FX / Q)")
    PLC_SERIES = series


def _parse_offset(dev: str, offset_str: str) -> int:
    """设备编号字符串 -> 帧内数值。

    非 X/Y 设备一律十进制；X/Y 按 PLC 系列进制：
      FX 系列 X/Y 为八进制编号（仅允许 0-7，X8/X9 等非法编号直接拒绝，
      不做静默别名）；Q/iQ-R 系列 X/Y 为十六进制编号。
    正则 `\\d+` 可匹配 Unicode 数字，此处显式校验 ASCII 字符集，
    非 ASCII 数字一律拒绝（fail-closed），避免 int(base) 抛 ValueError。
    """
    if dev in ("X", "Y"):
        if PLC_SERIES == "FX":
            if any(ch not in "01234567" for ch in offset_str):
                raise MCFrameError(
                    f"无效的 {dev} 设备编号: {dev}{offset_str} "
                    f"(FX 系列 X/Y 为八进制编号，仅允许数字 0-7)"
                )
            return int(offset_str, 8)
        # Q/iQ-R 十六进制编号（当前正则仅接受数字后缀，X1A 等字母后缀会
        # 在 _parse_device 的正则处被拒绝，属已知限制）
        if any(ch not in "0123456789" for ch in offset_str):
            raise MCFrameError(
                f"无效的 {dev} 设备编号: {dev}{offset_str} "
                f"(Q 系列 X/Y 为十六进制编号，仅允许数字 0-9)"
            )
        return int(offset_str, 16)
    try:
        return int(offset_str, 10)
    except ValueError:
        raise MCFrameError(
            f"无效的 {dev} 设备编号: {dev}{offset_str} (设备编号应为十进制数字)"
        )


def _parse_device(addr: str) -> tuple[int, int]:
    """解析设备地址 'M100' -> (0x90, 100)

    X/Y 设备编号按 PLC 系列进制解析（FX 八进制 / Q 十六进制），
    非法编号直接拒绝（fail-closed），不做静默别名。
    """
    m = re.match(r"^([A-Z]+)(\d+)$", addr.upper())
    if not m:
        raise MCFrameError(f"无效地址: {addr}")
    dev, offset_str = m.group(1), m.group(2)
    code = DEVICE_CODES.get(dev)
    if code is None:
        raise MCFrameError(f"不支持的设备类型: {dev}")
    offset = _parse_offset(dev, offset_str)
    if offset > MAX_DEVICE_OFFSET:
        raise MCFrameError(
            f"设备编号超出 3 字节可编码范围: {dev}{offset_str} (最大 {MAX_DEVICE_OFFSET})"
        )
    return code, offset


def _device_prefix(addr: str) -> str:
    """提取设备类型前缀"""
    return addr.upper().rstrip("0123456789")


def is_bit_device(addr: str) -> bool:
    """位设备: M, X, Y, L, B, T, C, S, V, F
    字设备: D, W, TN, CN, Z, ZR, R, SW
    """
    prefix = _device_prefix(addr)
    return prefix in ("M", "X", "Y", "L", "B", "T", "C", "S", "V", "F")


def _build_header(data_length: int) -> bytes:
    """构建 3E Binary 请求帧头（7 字节固定 + 2 字节 DataLen）"""
    header = struct.pack("<H", SUBHEADER_REQ)
    header += struct.pack("<B", NETWORK_NO)
    header += struct.pack("<B", PC_NO)
    header += struct.pack("<H", DEST_IO)
    header += struct.pack("<B", DEST_STATION)
    header += struct.pack("<H", data_length)
    return header


def _check_response_len(data: bytes) -> None:
    """校验响应头 DataLen 字段（offset 7-9）与实际帧长度一致，防止半包/错位帧被误解析"""
    declared = struct.unpack("<H", data[7:9])[0]
    actual = len(data) - RESP_HEADER_LEN
    if declared != actual:
        raise MCFrameError(
            f"响应数据长度不匹配: 声明 {declared} 字节, 实际 {actual} 字节"
        )


def build_read_request(addr: str, count: int = 1) -> bytes:
    """构建批量读取帧

    帧体: Timer(2) + Cmd(2) + SubCmd(2) + HeadDevice(3) + DevCode(1) + Points(2) = 12 字节
    """
    if not (1 <= count <= 0xFFFF):
        raise MCFrameError(f"读取点数超出范围: {count} (允许 1 ~ 65535)")
    code, offset = _parse_device(addr)
    subcmd = SUBCMD_BIT if code in _BIT_DEVICE_CODES else SUBCMD_WORD

    # 帧体（DataLen 之后的部分）
    body = struct.pack("<H", MONITOR_TIMER)
    body += struct.pack("<H", CMD_BATCH_READ)
    body += struct.pack("<H", subcmd)
    body += struct.pack("<I", offset)[:3]   # 起始设备编号 3 字节
    body += struct.pack("<B", code)          # 设备代码 1 字节
    body += struct.pack("<H", count)         # 设备点数 2 字节

    return _build_header(len(body)) + body


def build_write_request(addr: str, value: int) -> bytes:
    """构建单点写入帧

    帧体: Timer(2) + Cmd(2) + SubCmd(2) + HeadDevice(3) + DevCode(1) + Points(2) + Data
    """
    code, offset = _parse_device(addr)
    if code == DEVICE_CODES["X"]:
        raise MCFrameError(f"X 输入设备只读，禁止写入: {addr}")
    is_bit = code in _BIT_DEVICE_CODES
    subcmd = SUBCMD_BIT if is_bit else SUBCMD_WORD

    body = struct.pack("<H", MONITOR_TIMER)
    body += struct.pack("<H", CMD_BATCH_WRITE)
    body += struct.pack("<H", subcmd)
    body += struct.pack("<I", offset)[:3]
    body += struct.pack("<B", code)
    body += struct.pack("<H", 1)  # 写 1 点

    if is_bit:
        # 位写入: 1 字节 (0x10=ON, 0x00=OFF)
        body += struct.pack("<B", 0x10 if value else 0x00)
    else:
        # 字写入: 2 字节 LE（先校验 16 位可表示范围，超范围直接拒绝，不做静默截断）
        if not isinstance(value, int) or not (-0x8000 <= value <= 0xFFFF):
            raise MCFrameError(
                f"字写入值超出 16 位范围: {value!r} (允许整数 -32768 ~ 65535)"
            )
        body += struct.pack("<H", value & 0xFFFF)

    return _build_header(len(body)) + body


def parse_read_response(data: bytes, addr: str) -> list[int]:
    """解析读取响应

    响应头 9 字节后是 EndCode(2) + Data
    """
    if len(data) < RESP_HEADER_LEN + 2:
        raise MCFrameError(f"响应过短: {len(data)} bytes (最少 {RESP_HEADER_LEN + 2})")

    # 验证子头
    subheader = struct.unpack("<H", data[0:2])[0]
    if subheader != SUBHEADER_RESP:
        raise MCFrameError(f"无效响应子头: 0x{subheader:04X} (期望 0xD000)")

    _check_response_len(data)

    # EndCode 在 offset 9
    end_code = struct.unpack("<H", data[RESP_HEADER_LEN:RESP_HEADER_LEN + 2])[0]
    if end_code != 0:
        raise MCFrameError(f"PLC 返回错误码: 0x{end_code:04X}")

    # 数据从 offset 11 开始
    payload = data[RESP_HEADER_LEN + 2:]
    if is_bit_device(addr):
        # 位设备: 每个点占半字节 (4 bits)
        result = []
        for byte in payload:
            result.append(byte & 0x01)
            result.append((byte >> 4) & 0x01)
        return result
    else:
        # 字设备: 每个点 2 字节 LE（批量解包）
        if len(payload) % 2 != 0:
            raise MCFrameError(f"字数据长度异常: {len(payload)} 字节")
        return list(struct.unpack(f"<{len(payload) // 2}H", payload))


def parse_write_response(data: bytes) -> bool:
    """解析写入响应"""
    if len(data) < RESP_HEADER_LEN + 2:
        raise MCFrameError(f"响应过短: {len(data)} bytes (最少 {RESP_HEADER_LEN + 2})")

    # 验证子头（与读路径一致，防止错位/残留帧被误判为写入成功）
    subheader = struct.unpack("<H", data[0:2])[0]
    if subheader != SUBHEADER_RESP:
        raise MCFrameError(f"无效响应子头: 0x{subheader:04X} (期望 0xD000)")

    _check_response_len(data)

    end_code = struct.unpack("<H", data[RESP_HEADER_LEN:RESP_HEADER_LEN + 2])[0]
    if end_code != 0:
        raise MCFrameError(f"写入错误码: 0x{end_code:04X}")
    return True
