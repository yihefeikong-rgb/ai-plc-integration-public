"""
三菱 MC 协议（MELSEC Communication Protocol）
Binary 模式，TCP 传输，支持 FX3U/FX5U

帧结构:
  请求: SUB_HEADER(2) + PC_NO(1) + MONITOR_TIMER(2) + BODY_LEN(2) + CMD(2) + SUB_CMD(2) + BODY
  响应: SUB_HEADER(2) + PC_NO(1) + MONITOR_TIMER(2) + DATA_LEN(2) + END_CODE(2) + DATA
"""

import struct
import re
from enum import IntEnum

SUB_HEADER_REQ = b"\x50\x00"
SUB_HEADER_RESP = b"\xD0\x00"
PC_NO = b"\xFF"
MONITOR_TIMER = b"\x10\x00"

CMD_BATCH_READ = 0x0401
CMD_BATCH_WRITE = 0x1401

SUB_CMD_READ_BIT = b"\x01\x00\x01"
SUB_CMD_READ_WORD = b"\x01\x00\x00"
SUB_CMD_WRITE_BIT = b"\x01\x00\x01"
SUB_CMD_WRITE_WORD = b"\x01\x00\x00"

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


def is_bit_device(addr: str) -> bool:
    return addr[0].upper() in "MXYLBTXC"


def build_read_request(addr: str, count: int = 1) -> bytes:
    """构建批量读取帧"""
    code, offset = _parse_device(addr)
    is_bit = is_bit_device(addr)

    body = struct.pack("<B", code)
    body += struct.pack("<I", offset)[:3]
    body += b"\x00"
    body += struct.pack("<H", count)

    if is_bit:
        body += SUB_CMD_READ_BIT
    else:
        body += SUB_CMD_READ_WORD

    frame = SUB_HEADER_REQ + PC_NO + MONITOR_TIMER
    frame += struct.pack("<H", len(body))
    frame += struct.pack("<H", CMD_BATCH_READ)
    frame += b"\x00\x00"
    frame += body
    return frame


def build_write_request(addr: str, value: int) -> bytes:
    """构建单个写入帧"""
    code, offset = _parse_device(addr)
    is_bit = is_bit_device(addr)

    body = struct.pack("<B", code)
    body += struct.pack("<I", offset)[:3]
    body += b"\x00"
    body += struct.pack("<H", 1)

    if is_bit:
        body += b"\x00"
        body += struct.pack("<H", 1 if value else 0)
        body += SUB_CMD_WRITE_BIT
    else:
        body += b"\x00"
        body += struct.pack("<H", value & 0xFFFF)
        body += SUB_CMD_WRITE_WORD

    frame = SUB_HEADER_REQ + PC_NO + MONITOR_TIMER
    frame += struct.pack("<H", len(body))
    frame += struct.pack("<H", CMD_BATCH_WRITE)
    frame += b"\x00\x00"
    frame += body
    return frame


def parse_read_response(data: bytes, addr: str) -> list[int]:
    """解析读取响应"""
    if len(data) < 6:
        raise MCFrameError(f"响应过短: {len(data)} bytes")
    end_code = struct.unpack("<H", data[4:6])[0]
    if end_code != 0:
        raise MCFrameError(f"PLC 返回错误码: 0x{end_code:04X}")

    payload = data[6:]
    if is_bit_device(addr):
        count = len(payload) * 2
        return [(payload[i // 2] >> (i % 2) * 4) & 1 for i in range(count)]
    else:
        return [struct.unpack("<H", payload[i:i + 2])[0] for i in range(0, len(payload), 2)]


def parse_write_response(data: bytes) -> bool:
    """解析写入响应"""
    if len(data) < 6:
        raise MCFrameError(f"响应过短: {len(data)} bytes")
    end_code = struct.unpack("<H", data[4:6])[0]
    if end_code != 0:
        raise MCFrameError(f"写入错误码: 0x{end_code:04X}")
    return True
