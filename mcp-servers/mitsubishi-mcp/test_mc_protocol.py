"""
三菱 MC 协议单元测试 — 3E Binary 帧结构、设备解析、响应解析
不依赖硬件，验证协议层的内部一致性

3E Binary 响应帧:
  Subheader(2) + Network(1) + PC(1) + DestIO(2) + Station(1) + DataLen(2) + EndCode(2) + Data
  头 9 字节，EndCode 在 offset 9，数据从 offset 11 开始
"""

import struct
import pytest
from mc_protocol import (
    _parse_device, is_bit_device,
    build_read_request, build_write_request,
    parse_read_response, parse_write_response,
    MCFrameError, DEVICE_CODES, RESP_HEADER_LEN,
    SUBHEADER_REQ, SUBHEADER_RESP,
)


# ── 帮助函数 ──

def _make_resp_header(end_code: int = 0, data_len: int = 2) -> bytes:
    """构造标准 3E Binary 响应头（9 字节）+ EndCode（2 字节）"""
    header = struct.pack("<H", SUBHEADER_RESP)  # subheader
    header += struct.pack("<B", 0x00)           # network
    header += struct.pack("<B", 0xFF)           # pc
    header += struct.pack("<H", 0x03FF)         # dest io
    header += struct.pack("<B", 0x00)           # dest station
    header += struct.pack("<H", data_len)       # data length (incl end_code + data)
    header += struct.pack("<H", end_code)       # end code
    return header


def _make_read_response(values: list[int], addr: str) -> bytes:
    """构造模拟读响应（标准 3E Binary 格式）"""
    if is_bit_device(addr):
        byte_count = (len(values) + 1) // 2
        raw = bytearray(byte_count)
        for i, v in enumerate(values):
            nibble = i % 2
            raw[i // 2] |= (v & 1) << (nibble * 4)
        payload = bytes(raw)
    else:
        payload = b"".join(struct.pack("<H", v) for v in values)
    data_len = 2 + len(payload)  # EndCode(2) + payload
    return _make_resp_header(end_code=0, data_len=data_len) + payload


def _make_write_response(end_code: int = 0) -> bytes:
    """构造写响应"""
    return _make_resp_header(end_code=end_code, data_len=2)


# =============================================
# 设备地址解析
# =============================================

class TestParseDevice:
    def test_d_register(self):
        code, offset = _parse_device("D100")
        assert code == 0xA8
        assert offset == 100

    def test_m_relay(self):
        code, offset = _parse_device("M0")
        assert code == 0x90
        assert offset == 0

    def test_x_input(self):
        code, offset = _parse_device("X10")
        assert code == 0x9C
        assert offset == 10

    def test_y_output(self):
        code, offset = _parse_device("Y20")
        assert code == 0x9D
        assert offset == 20

    def test_large_address(self):
        code, offset = _parse_device("D65535")
        assert code == 0xA8
        assert offset == 65535

    def test_case_insensitive(self):
        code1, off1 = _parse_device("d100")
        code2, off2 = _parse_device("D100")
        assert code1 == code2 == 0xA8
        assert off1 == off2 == 100

    def test_empty_string_raises(self):
        with pytest.raises(MCFrameError, match="无效地址"):
            _parse_device("")

    def test_invalid_format_raises(self):
        with pytest.raises(MCFrameError, match="无效地址"):
            _parse_device("ABC")

    def test_unknown_device_raises(self):
        with pytest.raises(MCFrameError, match="不支持的设备类型"):
            _parse_device("Z100")

    def test_no_number_raises(self):
        with pytest.raises(MCFrameError):
            _parse_device("D")

    def test_all_supported_devices(self):
        for dev_name in DEVICE_CODES:
            code, _ = _parse_device(f"{dev_name}0")
            assert code == DEVICE_CODES[dev_name], f"Failed for {dev_name}"


# =============================================
# 位/字设备判断
# =============================================

class TestIsBitDevice:
    def test_m_is_bit(self):
        assert is_bit_device("M100")

    def test_x_is_bit(self):
        assert is_bit_device("X10")

    def test_y_is_bit(self):
        assert is_bit_device("Y20")

    def test_d_is_word(self):
        assert not is_bit_device("D100")

    def test_w_is_word(self):
        assert not is_bit_device("W10")

    def test_t_is_bit(self):
        assert is_bit_device("T0")

    def test_tn_is_word(self):
        assert not is_bit_device("TN0")


# =============================================
# 读请求帧结构
# =============================================

class TestBuildReadRequest:
    # 请求头: Subheader(2) + Net(1) + PC(1) + IO(2) + Station(1) + DataLen(2) = 9 bytes
    REQ_HEADER_LEN = 9

    def test_starts_with_correct_subheader(self):
        frame = build_read_request("D100", 1)
        subheader = struct.unpack("<H", frame[0:2])[0]
        assert subheader == SUBHEADER_REQ

    def test_network_and_pc(self):
        frame = build_read_request("D100", 1)
        assert frame[2] == 0x00  # network
        assert frame[3] == 0xFF  # pc

    def test_dest_io_and_station(self):
        frame = build_read_request("D100", 1)
        dest_io = struct.unpack("<H", frame[4:6])[0]
        assert dest_io == 0x03FF
        assert frame[6] == 0x00  # station

    def test_data_length_field(self):
        frame = build_read_request("D100", 1)
        data_len = struct.unpack("<H", frame[7:9])[0]
        actual_body = frame[self.REQ_HEADER_LEN:]
        assert len(actual_body) == data_len

    def test_has_read_command(self):
        frame = build_read_request("D100", 1)
        # 帧体: Timer(2) + Cmd(2)... Cmd 在 offset 9+2=11
        cmd = struct.unpack("<H", frame[11:13])[0]
        assert cmd == 0x0401

    def test_has_monitor_timer(self):
        frame = build_read_request("D100", 1)
        timer = struct.unpack("<H", frame[9:11])[0]
        assert timer == 0x0010

    def test_word_subcmd(self):
        frame = build_read_request("D100", 1)
        subcmd = struct.unpack("<H", frame[13:15])[0]
        assert subcmd == 0x0000  # SUBCMD_WORD

    def test_bit_subcmd(self):
        frame = build_read_request("M100", 1)
        subcmd = struct.unpack("<H", frame[13:15])[0]
        assert subcmd == 0x0001  # SUBCMD_BIT

    def test_device_address_encoding(self):
        frame = build_read_request("D200", 1)
        # 帧体从 offset 9 开始: Timer(2) + Cmd(2) + SubCmd(2) + HeadDev(3) + DevCode(1) + Points(2)
        # HeadDev at offset 9+6=15, 3 bytes
        head_dev = frame[15:18]
        assert head_dev == struct.pack("<I", 200)[:3]

    def test_device_code(self):
        frame = build_read_request("D200", 1)
        # DevCode at offset 9+6+3=18, 1 byte
        assert frame[18] == 0xA8

    def test_point_count(self):
        frame = build_read_request("D100", 5)
        # Points at offset 9+6+3+1=19, 2 bytes
        points = struct.unpack("<H", frame[19:21])[0]
        assert points == 5

    def test_read_frame_total_length(self):
        # Header(9) + Timer(2) + Cmd(2) + SubCmd(2) + HeadDev(3) + DevCode(1) + Points(2) = 21
        frame = build_read_request("D100", 1)
        assert len(frame) == 21


# =============================================
# 写请求帧结构
# =============================================

class TestBuildWriteRequest:
    REQ_HEADER_LEN = 9

    def test_has_write_command(self):
        frame = build_write_request("D100", 500)
        cmd = struct.unpack("<H", frame[11:13])[0]
        assert cmd == 0x1401

    def test_write_word_value(self):
        frame = build_write_request("D100", 1234)
        # Data at offset 9+6+3+1+2=21, 2 bytes for word write
        value = struct.unpack("<H", frame[21:23])[0]
        assert value == 1234

    def test_write_bit_on(self):
        frame = build_write_request("M100", 1)
        # Bit data at offset 21, 1 byte (0x10=ON)
        assert frame[21] == 0x10

    def test_write_bit_off(self):
        frame = build_write_request("M100", 0)
        assert frame[21] == 0x00

    def test_write_large_value_truncated(self):
        frame = build_write_request("D100", 0x1FFFF)
        value = struct.unpack("<H", frame[21:23])[0]
        assert value == 0xFFFF

    def test_write_word_frame_length(self):
        # Header(9) + Timer(2) + Cmd(2) + SubCmd(2) + HeadDev(3) + DevCode(1) + Points(2) + Value(2) = 23
        frame = build_write_request("D100", 500)
        assert len(frame) == 23

    def test_write_bit_frame_length(self):
        # Header(9) + Timer(2) + Cmd(2) + SubCmd(2) + HeadDev(3) + DevCode(1) + Points(2) + BitVal(1) = 22
        frame = build_write_request("M100", 1)
        assert len(frame) == 22


# =============================================
# 读响应解析
# =============================================

class TestParseReadResponse:

    def test_parse_word_one_value(self):
        resp = _make_read_response([100], "D100")
        values = parse_read_response(resp, "D100")
        assert values == [100]

    def test_parse_word_multiple(self):
        resp = _make_read_response([1, 100, 65535], "D100")
        values = parse_read_response(resp, "D100")
        assert values == [1, 100, 65535]

    def test_parse_bit_values(self):
        resp = _make_read_response([1, 0, 1, 0], "M100")
        values = parse_read_response(resp, "M100")
        assert len(values) == 4
        assert values == [1, 0, 1, 0]

    def test_parse_zero(self):
        resp = _make_read_response([0], "D100")
        values = parse_read_response(resp, "D100")
        assert values == [0]

    def test_parse_max_word(self):
        resp = _make_read_response([0xFFFF], "D100")
        values = parse_read_response(resp, "D100")
        assert values == [65535]

    def test_parse_empty(self):
        resp = _make_resp_header(end_code=0, data_len=2)
        values = parse_read_response(resp, "D100")
        assert values == []

    def test_error_end_code_raises(self):
        resp = _make_resp_header(end_code=0x05C0, data_len=2)
        with pytest.raises(MCFrameError, match="错误码"):
            parse_read_response(resp, "D100")

    def test_short_response_raises(self):
        with pytest.raises(MCFrameError, match="过短"):
            parse_read_response(b"\x00\x00\x00", "D100")

    def test_invalid_subheader_raises(self):
        bad = b"\x50\x00" + b"\x00" * 9  # wrong subheader
        with pytest.raises(MCFrameError, match="无效响应子头"):
            parse_read_response(bad, "D100")


# =============================================
# 写响应解析
# =============================================

class TestParseWriteResponse:

    def test_success(self):
        resp = _make_write_response(end_code=0)
        assert parse_write_response(resp)

    def test_error_raises(self):
        resp = _make_write_response(end_code=0x05C0)
        with pytest.raises(MCFrameError, match="写入错误码"):
            parse_write_response(resp)

    def test_short_raises(self):
        with pytest.raises(MCFrameError, match="过短"):
            parse_write_response(b"\x00\x00")


# =============================================
# 边界和错误情况
# =============================================

class TestEdgeCases:

    def test_zero_address(self):
        code, offset = _parse_device("D0")
        assert offset == 0
        assert code == 0xA8

    def test_max_address_encoding(self):
        frame = build_read_request("D65535", 1)
        # HeadDevice at offset 15
        addr_bytes = frame[15:18]
        assert addr_bytes == struct.pack("<I", 65535)[:3]

    def test_build_write_zero(self):
        frame = build_write_request("D100", 0)
        assert len(frame) > 0

    def test_build_write_negative(self):
        """负值按无符号 16 位编码"""
        frame = build_write_request("D100", -1)
        value = struct.unpack("<H", frame[21:23])[0]
        assert value == 0xFFFF


# =============================================
# 往返一致性
# =============================================

class TestRoundTrip:

    def test_read_word_roundtrip(self):
        values = [42, 999, 12345]
        resp = _make_read_response(values, "D100")
        result = parse_read_response(resp, "D100")
        assert result == values

    def test_read_bit_roundtrip(self):
        values = [1, 0, 1, 0, 1, 1, 0, 0]
        resp = _make_read_response(values, "M100")
        result = parse_read_response(resp, "M100")
        assert result[:len(values)] == values

    def test_different_devices_same_header(self):
        """不同设备类型的请求头（前 9 字节）应相同"""
        frame_d = build_read_request("D100", 1)
        frame_m = build_read_request("M100", 1)
        assert frame_d[:9] == frame_m[:9]
        # 但设备代码不同
        assert frame_d[18] != frame_m[18]
