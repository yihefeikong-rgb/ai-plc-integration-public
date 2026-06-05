"""
三菱 MC 协议单元测试 — 帧结构、设备解析、响应解析
不依赖硬件，验证协议层的内部一致性

注意：代码中 parse_read_response 期望的响应格式为：
  [subheader 2B] [?? 2B] [end_code 2B] [data...]
所以 mock 响应也按此结构构造。
"""

import struct
import pytest
from mc_protocol import (
    _parse_device, is_bit_device,
    build_read_request, build_write_request,
    parse_read_response, parse_write_response,
    MCFrameError, DEVICE_CODES,
)

# Helper: build a mock read response that matches parse_read_response's layout
def _make_read_response(values: list[int], addr: str) -> bytes:
    """构造模拟读响应：
    data[0:2] = subheader (D0 00)
    data[2:4] = ?? padding
    data[4:6] = end_code
    data[6:]  = data values
    """
    if is_bit_device(addr):
        # bits packed 4 per byte (nibble)
        byte_count = (len(values) + 1) // 2
        raw = bytearray(byte_count)
        for i, v in enumerate(values):
            nibble = i % 2
            raw[i // 2] |= (v & 1) << (nibble * 4)
        payload = bytes(raw)
    else:
        payload = b"".join(struct.pack("<H", v) for v in values)
    return b"\xD0\x00\x00\x00\x00\x00" + payload


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
        """T（定时器触点）当前实现中按位设备处理"""
        assert is_bit_device("T0")

    def test_tn_is_word(self):
        """TN（定时器当前值）按字设备"""
        assert not is_bit_device("TN0")


# =============================================
# 读请求帧结构
# =============================================

class TestBuildReadRequest:
    REQ_HEADER_LEN = 11  # subheader(2) + PC(1) + timer(2) + bodyLen(2) + cmd(2) + subcmd(2)

    def test_starts_with_header(self):
        frame = build_read_request("D100", 1)
        assert frame[:2] == b"\x50\x00"

    def test_has_pc_and_timer(self):
        frame = build_read_request("D100", 1)
        assert frame[2:3] == b"\xFF"
        assert frame[3:5] == b"\x10\x00"

    def test_has_read_command(self):
        frame = build_read_request("D100", 1)
        cmd = struct.unpack("<H", frame[7:9])[0]
        assert cmd == 0x0401

    def test_body_length_matches(self):
        frame = build_read_request("D100", 1)
        body_len = struct.unpack("<H", frame[5:7])[0]
        actual_body = frame[self.REQ_HEADER_LEN:]
        assert len(actual_body) == body_len

    def test_contains_device_code(self):
        frame = build_read_request("D200", 1)
        body = frame[self.REQ_HEADER_LEN:]
        assert body[0:1] == b"\xA8"

    def test_contains_address(self):
        frame = build_read_request("D200", 1)
        body = frame[self.REQ_HEADER_LEN:]
        addr_bytes = body[1:4]
        assert addr_bytes == struct.pack("<I", 200)[:3]

    def test_word_read_subcmd(self):
        frame = build_read_request("D100", 1)
        body = frame[self.REQ_HEADER_LEN:]
        assert body[7:10] == b"\x01\x00\x00"  # SUB_CMD_READ_WORD

    def test_bit_read_subcmd(self):
        frame = build_read_request("M100", 1)
        body = frame[self.REQ_HEADER_LEN:]
        assert body[7:10] == b"\x01\x00\x01"  # SUB_CMD_READ_BIT

    def test_multi_point_read(self):
        frame = build_read_request("D100", 5)
        body = frame[self.REQ_HEADER_LEN:]
        count = struct.unpack("<H", body[5:7])[0]
        assert count == 5

    def test_read_frame_length(self):
        frame = build_read_request("D100", 1)
        assert len(frame) == 21


# =============================================
# 写请求帧结构
# =============================================

class TestBuildWriteRequest:
    REQ_HEADER_LEN = 11

    def test_has_write_command(self):
        frame = build_write_request("D100", 500)
        cmd = struct.unpack("<H", frame[7:9])[0]
        assert cmd == 0x1401

    def test_write_word_value_at_correct_offset(self):
        """字设备写入值在 body[8:10]"""
        frame = build_write_request("D100", 1234)
        body = frame[self.REQ_HEADER_LEN:]
        value = struct.unpack("<H", body[8:10])[0]
        assert value == 1234

    def test_write_bit_on(self):
        frame = build_write_request("M100", 1)
        body = frame[self.REQ_HEADER_LEN:]
        value = struct.unpack("<H", body[8:10])[0]
        assert value == 1

    def test_write_bit_off(self):
        frame = build_write_request("M100", 0)
        body = frame[self.REQ_HEADER_LEN:]
        value = struct.unpack("<H", body[8:10])[0]
        assert value == 0

    def test_write_bit_nonzero(self):
        """位设备非零值 → 1"""
        frame = build_write_request("M100", 255)
        body = frame[self.REQ_HEADER_LEN:]
        value = struct.unpack("<H", body[8:10])[0]
        assert value == 1

    def test_write_large_value_truncated(self):
        """超过 16 位的值应截断"""
        frame = build_write_request("D100", 0x1FFFF)
        body = frame[self.REQ_HEADER_LEN:]
        value = struct.unpack("<H", body[8:10])[0]
        assert value == 0xFFFF

    def test_write_frame_length(self):
        frame = build_write_request("D100", 500)
        assert len(frame) == 24


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
        # nibble order: low nibble first
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
        resp = b"\xD0\x00\x00\x00\x00\x00"
        values = parse_read_response(resp, "D100")
        assert values == []

    def test_error_end_code_raises(self):
        resp = b"\xD0\x00\x00\x00\xC0\x05"
        with pytest.raises(MCFrameError, match="错误码"):
            parse_read_response(resp, "D100")

    def test_short_response_raises(self):
        with pytest.raises(MCFrameError, match="过短"):
            parse_read_response(b"\x00\x00\x00", "D100")


# =============================================
# 写响应解析
# =============================================

class TestParseWriteResponse:

    def test_success(self):
        resp = b"\xD0\x00\x00\x00\x00\x00"
        assert parse_write_response(resp)

    def test_error_raises(self):
        resp = b"\xD0\x00\x00\x00\xC0\x05"
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
        body = frame[11:]
        addr_bytes = body[1:4]
        assert addr_bytes == struct.pack("<I", 65535)[:3]

    def test_negative_count_raises(self):
        """负 count 触发 struct.error"""
        with pytest.raises(struct.error):
            build_read_request("D100", -1)

    def test_build_write_zero(self):
        frame = build_write_request("D100", 0)
        assert len(frame) > 0

    def test_build_write_negative(self):
        """负值也能编码（二进制补码）"""
        frame = build_write_request("D100", -1)
        body = frame[11:]
        value = struct.unpack("<H", body[8:10])[0]
        assert value == 0xFFFF  # -1 as unsigned 16-bit


# =============================================
# 往返一致性
# =============================================

class TestRoundTrip:

    def test_read_word_roundtrip(self):
        """构建读请求 → 解析模拟响应"""
        values = [42, 999, 12345]
        resp = _make_read_response(values, "D100")
        result = parse_read_response(resp, "D100")
        assert result == values

    def test_read_bit_roundtrip(self):
        values = [1, 0, 1, 0, 1, 1, 0, 0]
        resp = _make_read_response(values, "M100")
        result = parse_read_response(resp, "M100")
        assert result[:len(values)] == values

    def test_different_devices_same_frame_structure(self):
        frame_d = build_read_request("D100", 1)
        frame_m = build_read_request("M100", 1)
        assert frame_d[:11] == frame_m[:11]
        assert frame_d[11:12] != frame_m[11:12]
