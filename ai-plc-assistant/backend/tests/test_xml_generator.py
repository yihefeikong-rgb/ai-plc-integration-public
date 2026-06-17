"""测试 generator/xml_generator.py — PLCopen XML 生成"""

import xml.etree.ElementTree as ET

from generator import LadderProgram
from generator.xml_generator import generate_xml


def _make_program():
    p = LadderProgram("TestBlock", "测试用 FB")
    p.add_variable("I0.0", "bStart", "Bool", "启动")
    p.add_variable("Q0.0", "qMotor", "Bool", "电机")
    p.add_variable("M0.0", "mFlag", "Bool", "标志")
    p.add_network(1, "逻辑1", "code", "注释")
    return p


class TestGenerateXML:
    def test_valid_xml(self):
        xml_str = generate_xml(_make_program())
        assert xml_str.startswith("<?xml")
        # 应能被解析
        root = ET.fromstring(xml_str)
        assert root.tag.endswith("project") or root.tag == "project"

    def test_fb_type(self):
        xml_str = generate_xml(_make_program(), block_type="FB")
        root = ET.fromstring(xml_str)
        # 查找 pouType
        ns = {"ns": "http://www.plcopen.org/xml/tc6_0201"}
        pou = root.find(".//pou") or root.find(".//{*}pou")
        if pou is not None:
            assert pou.get("pouType") == "functionBlock"

    def test_fc_type(self):
        xml_str = generate_xml(_make_program(), block_type="FC")
        assert "function" in xml_str.lower()

    def test_contains_variables(self):
        xml_str = generate_xml(_make_program())
        assert "bStart" in xml_str
        assert "qMotor" in xml_str

    def test_contains_networks(self):
        xml_str = generate_xml(_make_program())
        assert "Network 1" in xml_str or "逻辑1" in xml_str

    def test_custom_name(self):
        xml_str = generate_xml(_make_program(), block_name="MyCustomBlock")
        assert "MyCustomBlock" in xml_str

    def test_empty_program(self):
        p = LadderProgram("Empty", "")
        xml_str = generate_xml(p)
        root = ET.fromstring(xml_str)
        assert root is not None
