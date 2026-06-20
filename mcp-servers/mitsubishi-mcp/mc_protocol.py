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
}


class MCFrameError(Exception):
    pass


def _parse_device(addr: str) -> tuple[int, int]:
    """解析设备地址 'M100' -> (0x90, 100)"""
    m = re.match(r"^([A-Z]+)(\d+)$", addr.upper())
    if not m:
        raise MCFrameError(f"无效地址: {addr}")
    dev, offset = m.group(1), int(m.group(2))
    code = DEVICE_CODES.get(dev)
    if code is None:
        raise MCFrameError(f"不支持的设备类型: {dev}")
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


def build_read_request(addr: str, count: int = 1) -> bytes:
    """构建批量读取帧

    帧体: Timer(2) + Cmd(2) + SubCmd(2) + HeadDevice(3) + DevCode(1) + Points(2) = 12 字节
    """
    code, offset = _parse_device(addr)
    subcmd = SUBCMD_BIT if is_bit_device(addr) else SUBCMD_WORD

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
    is_bit = is_bit_device(addr)
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
        # 字写入: 2 字节 LE
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

    # EndCode 在 offset 9
    end_code = struct.unpack("<H", data[RESP_HEADER_LEN:RESP_HEADER_LEN + 2])[0]
    if end_code != 0:
        raise MCFrameError(f"PLC 返回错误码: 0x{end_code:04X}")

    # 数据从 offset 11 开始
    payload = data[RESP_HEADER_LEN + 2:]
    if is_bit_device(addr):
        # 位设备: 每个点占半字节 (4 bits)
        count = len(payload) * 2
        return [(payload[i // 2] >> (i % 2) * 4) & 1 for i in range(count)]
    else:
        # 字设备: 每个点 2 字节 LE
        return [struct.unpack("<H", payload[i:i + 2])[0]
                for i in range(0, len(payload), 2)]


def parse_write_response(data: bytes) -> bool:
    """解析写入响应"""
    if len(data) < RESP_HEADER_LEN + 2:
        raise MCFrameError(f"响应过短: {len(data)} bytes (最少 {RESP_HEADER_LEN + 2})")

    end_code = struct.unpack("<H", data[RESP_HEADER_LEN:RESP_HEADER_LEN + 2])[0]
    if end_code != 0:
        raise MCFrameError(f"写入错误码: 0x{end_code:04X}")
    return True
