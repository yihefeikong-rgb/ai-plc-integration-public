"""测试 search/parsers.py — PLC 文件结构化解析"""

from search.parsers import parse_file


class TestParseSCL:
    def test_parse_scl_block(self, sample_scl_file):
        entries = parse_file(sample_scl_file)
        assert len(entries) > 0

        # 应识别出 FUNCTION_BLOCK
        block_entries = [e for e in entries if e["type"] == "plc_block"]
        assert len(block_entries) >= 1
        assert block_entries[0]["name"] == "MotorControl"
        assert block_entries[0]["block_type"] == "FB"

    def test_parse_scl_variables(self, sample_scl_file):
        entries = parse_file(sample_scl_file)
        var_entries = [e for e in entries if e["type"] == "variable"]
        var_names = [e["name"] for e in var_entries]
        assert "bStart" in var_names
        assert "bStop" in var_names
        assert "qMotor" in var_names

    def test_parse_scl_fc(self, tmp_path):
        content = 'FUNCTION "CalcSpeed" : Real\nVAR_INPUT\n    rInput : Real;\nEND_VAR\nBEGIN\n    CalcSpeed := rInput * 2.0;\nEND_FUNCTION'
        p = tmp_path / "CalcSpeed.scl"
        p.write_text(content, encoding="utf-8")
        entries = parse_file(str(p))
        blocks = [e for e in entries if e["type"] == "plc_block"]
        assert blocks[0]["block_type"] == "FC"
        assert blocks[0]["name"] == "CalcSpeed"


class TestParseCSV:
    def test_parse_csv_io_table(self, sample_csv_file):
        entries = parse_file(sample_csv_file)
        assert len(entries) > 0
        io_entries = [e for e in entries if e["type"] == "io_entry"]
        assert len(io_entries) == 3
        names = [e["name"] for e in io_entries]
        assert "bStart" in names

    def test_parse_csv_empty(self, tmp_path):
        p = tmp_path / "empty.csv"
        p.write_text("Name,Address\n", encoding="utf-8")
        entries = parse_file(str(p))
        assert len(entries) == 0


class TestParseXML:
    def test_parse_xml_block(self, sample_xml_file):
        entries = parse_file(sample_xml_file)
        assert len(entries) > 0
        blocks = [e for e in entries if e["type"] == "plc_block"]
        assert len(blocks) >= 1

    def test_parse_xml_returns_entries(self, sample_xml_file):
        """XML 解析应返回至少一个条目（块或变量）"""
        entries = parse_file(sample_xml_file)
        assert len(entries) >= 1
        # 检查 block 条目包含名称
        blocks = [e for e in entries if e["type"] == "plc_block"]
        assert blocks[0]["name"] == "TestBlock"


class TestParseGeneric:
    def test_parse_unknown_type(self, tmp_path):
        p = tmp_path / "test.udt"
        p.write_text("TYPE MyUDT\n  field1 : Int;\nEND_TYPE", encoding="utf-8")
        entries = parse_file(str(p))
        assert len(entries) > 0
