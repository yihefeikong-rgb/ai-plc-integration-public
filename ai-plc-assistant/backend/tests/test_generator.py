"""测试 generator/__init__.py — LadderProgram + parse_raw_output + Demo"""

from generator import LadderProgram, Variable, Network, parse_raw_output, build_demo_program
from tests.mock_llm import MOCK_CHAT_RESPONSE


class TestLadderProgram:
    def test_create_empty(self):
        p = LadderProgram("Test", "Description")
        assert p.title == "Test"
        assert p.description == "Description"
        assert p.variables == []
        assert p.networks == []

    def test_add_variable(self):
        p = LadderProgram("Test")
        p.add_variable("I0.0", "bStart", "Bool", "启动")
        assert len(p.variables) == 1
        assert p.variables[0].name == "bStart"
        assert p.variables[0].address == "I0.0"

    def test_add_network(self):
        p = LadderProgram("Test")
        p.add_network(1, "主逻辑", "code", "comment")
        assert len(p.networks) == 1
        assert p.networks[0].number == 1
        assert p.networks[0].title == "主逻辑"

    def test_to_dict(self):
        p = LadderProgram("Motor", "电机控制")
        p.add_variable("I0.0", "bStart", "Bool", "启动")
        p.add_network(1, "Network 1", "code", "comment")
        d = p.to_dict()
        assert d["title"] == "Motor"
        assert len(d["variables"]) == 1
        assert len(d["networks"]) == 1
        assert d["variables"][0]["name"] == "bStart"

    def test_to_text(self):
        p = LadderProgram("Motor", "电机控制")
        p.add_variable("I0.0", "bStart", "Bool", "启动")
        p.add_network(1, "启动", "| |--( )--", "自锁")
        text = p.to_text()
        assert "# Motor" in text
        assert "bStart" in text
        assert "Network 1" in text


class TestParseRawOutput:
    def test_parse_mock_response(self):
        """解析 mock LLM 输出为结构化数据"""
        program = parse_raw_output(MOCK_CHAT_RESPONSE)
        assert program.title != ""
        assert len(program.variables) >= 3
        assert len(program.networks) >= 2

    def test_parse_variables(self):
        program = parse_raw_output(MOCK_CHAT_RESPONSE)
        names = [v.name for v in program.variables]
        assert "bStart" in names
        assert "bStop" in names
        assert "qMotor" in names

    def test_parse_networks(self):
        program = parse_raw_output(MOCK_CHAT_RESPONSE)
        titles = [n.title for n in program.networks]
        assert any("启动" in t for t in titles)

    def test_parse_empty_input(self):
        program = parse_raw_output("")
        assert program.title == ""
        assert program.variables == []
        assert program.networks == []

    def test_parse_no_networks(self):
        text = "# Test\n\n> Desc\n\n## 变量表\n| I0.0 | x | Bool | test |"
        program = parse_raw_output(text)
        assert program.title == "Test"
        assert len(program.variables) >= 1


class TestBuildDemo:
    def test_motor_demo(self):
        p = build_demo_program("motor-start-stop", {})
        assert "电机" in p.title or "Motor" in p.title
        assert len(p.variables) >= 4
        assert len(p.networks) >= 2

    def test_traffic_light_demo(self):
        p = build_demo_program("traffic-light", {"green_time": "20"})
        assert len(p.variables) >= 6
        assert len(p.networks) >= 3

    def test_conveyor_demo(self):
        p = build_demo_program("conveyor", {})
        assert len(p.variables) >= 4
        assert len(p.networks) >= 2

    def test_unknown_template_fallback(self):
        p = build_demo_program("nonexistent", {})
        assert len(p.networks) >= 1  # 回退到电机 demo


class TestVariable:
    def test_to_dict(self):
        v = Variable("I0.0", "bStart", "Bool", "启动按钮")
        d = v.to_dict()
        assert d == {"address": "I0.0", "name": "bStart", "data_type": "Bool", "comment": "启动按钮"}


class TestNetwork:
    def test_to_text(self):
        n = Network(1, "启动", "code", "comment")
        text = n.to_text()
        assert "Network 1" in text
        assert "启动" in text
        assert "comment" in text

    def test_to_dict(self):
        n = Network(1, "标题", "代码", "注释")
        d = n.to_dict()
        assert d["number"] == 1
        assert d["title"] == "标题"
