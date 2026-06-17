"""测试 knowledge/parsers.py — 文件解析器"""

import pytest
from knowledge.parsers import parse_file, get_file_metadata


class TestParseTxt:
    def test_parse_txt(self, sample_txt_file):
        text = parse_file(sample_txt_file)
        assert "S7-1200" in text
        assert "PLC" in text
        assert "PROFINET" in text

    def test_parse_txt_empty(self, tmp_path):
        p = tmp_path / "empty.txt"
        p.write_text("", encoding="utf-8")
        text = parse_file(str(p))
        assert text == ""

    def test_parse_txt_chinese(self, tmp_path):
        p = tmp_path / "cn.txt"
        p.write_text("西门子PLC编程指南\n模拟量处理", encoding="utf-8")
        text = parse_file(str(p))
        assert "西门子" in text
        assert "模拟量" in text


class TestFileMetadata:
    def test_metadata(self, sample_txt_file):
        meta = get_file_metadata(sample_txt_file)
        assert meta["filename"] == "plc_guide.txt"
        assert meta["extension"] == ".txt"
        assert meta["size_bytes"] > 0
        assert meta["modified"] > 0


class TestUnsupportedFormat:
    def test_unsupported_extension(self, tmp_path):
        p = tmp_path / "test.xyz"
        p.write_text("content")
        with pytest.raises(ValueError, match="不支持"):
            parse_file(str(p))
