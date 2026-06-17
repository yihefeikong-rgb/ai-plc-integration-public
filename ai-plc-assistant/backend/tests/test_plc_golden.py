"""PLC Golden Dataset 回归测试 — 保护核心生成能力

改 Prompt / Agent / RAG / 模型都不能把 PLC 生成搞坏。
"""

import json
import os
from pathlib import Path

import pytest

from generator import LadderProgram, build_demo_program, parse_raw_output
from generator.scl_generator import generate_scl
from generator.xml_generator import generate_xml
from generator.export_generator import (
    generate_tag_csv, generate_hmi_tags, generate_alarm_list, generate_variable_json,
)
from tests.mock_llm import MOCK_CHAT_RESPONSE

GOLDEN_DIR = Path(__file__).parent / "golden"

def _load_datasets():
    with open(GOLDEN_DIR / "datasets.json", "r", encoding="utf-8") as f:
        return json.load(f)

def _make_program_from_vars(variables):
    """从变量列表创建 LadderProgram"""
    p = LadderProgram("GoldenTest", "回归测试")
    for v in variables:
        p.add_variable(v["address"], v["name"], v["data_type"], v.get("comment", ""))
    return p

DATASETS = _load_datasets()
DEMO_CASES = [d for d in DATASETS if d["source"] == "demo"]
EXPORT_SCL = [d for d in DATASETS if d["source"] == "export_scl"]
EXPORT_XML = [d for d in DATASETS if d["source"] == "export_xml"]
EXPORT_CSV = [d for d in DATASETS if d["source"] == "export_csv"]
EXPORT_HMI = [d for d in DATASETS if d["source"] == "export_hmi"]
EXPORT_ALARM = [d for d in DATASETS if d["source"] == "export_alarm"]
EXPORT_JSON = [d for d in DATASETS if d["source"] == "export_json"]
MOCK_LLM_CASES = [d for d in DATASETS if d["source"] == "mock_llm"]
API_CASES = [d for d in DATASETS if d["source"] == "api"]


# ---- Demo Generator 回归 ----

class TestDemoGenerators:
    @pytest.mark.parametrize("case", DEMO_CASES, ids=[c["id"] for c in DEMO_CASES])
    def test_demo_structure(self, case):
        """Demo 生成器输出结构验证"""
        program = build_demo_program(case["template_id"], case.get("variables", {}))

        # 变量数量
        assert len(program.variables) >= case["min_variables"], \
            f"{case['id']}: 变量数 {len(program.variables)} < {case['min_variables']}"

        # 网络数量
        assert len(program.networks) >= case["min_networks"], \
            f"{case['id']}: 网络数 {len(program.networks)} < {case['min_networks']}"

    @pytest.mark.parametrize("case", DEMO_CASES, ids=[c["id"] for c in DEMO_CASES])
    def test_demo_variables(self, case):
        """Demo 输出必须包含关键变量"""
        program = build_demo_program(case["template_id"], case.get("variables", {}))
        var_names = [v.name for v in program.variables]
        for expected in case["must_contain"]:
            assert expected in var_names, \
                f"{case['id']}: 缺少变量 '{expected}', 实际: {var_names}"

    @pytest.mark.parametrize("case", DEMO_CASES, ids=[c["id"] for c in DEMO_CASES])
    def test_demo_text_content(self, case):
        """Demo 文本输出必须包含关键词"""
        program = build_demo_program(case["template_id"], case.get("variables", {}))
        text = program.to_text()
        for keyword in case["must_contain_in_text"]:
            assert keyword in text, \
                f"{case['id']}: 文本缺少 '{keyword}'"


# ---- LLM Mock 解析回归 ----

class TestMockLLMParse:
    @pytest.mark.parametrize("case", MOCK_LLM_CASES, ids=[c["id"] for c in MOCK_LLM_CASES])
    def test_parse_structure(self, case):
        """Mock LLM 输出解析 — 结构验证"""
        program = parse_raw_output(MOCK_CHAT_RESPONSE)
        assert len(program.variables) >= case["min_variables"]
        assert len(program.networks) >= case["min_networks"]

    @pytest.mark.parametrize("case", MOCK_LLM_CASES, ids=[c["id"] for c in MOCK_LLM_CASES])
    def test_parse_variables(self, case):
        """Mock LLM 输出解析 — 变量提取"""
        program = parse_raw_output(MOCK_CHAT_RESPONSE)
        var_names = [v.name for v in program.variables]
        for expected in case["must_contain"]:
            assert expected in var_names, f"解析缺少变量 '{expected}'"

    @pytest.mark.parametrize("case", MOCK_LLM_CASES, ids=[c["id"] for c in MOCK_LLM_CASES])
    def test_parse_text(self, case):
        """Mock LLM 输出解析 — 文本内容"""
        program = parse_raw_output(MOCK_CHAT_RESPONSE)
        text = program.to_text()
        for keyword in case["must_contain_in_text"]:
            assert keyword in text


# ---- 导出格式回归 ----

def _motor_program():
    p = LadderProgram("MotorControl", "电机控制")
    p.add_variable("I0.0", "bStart", "Bool", "启动")
    p.add_variable("I0.1", "bStop", "Bool", "停止")
    p.add_variable("Q0.0", "qMotor", "Bool", "电机")
    p.add_variable("M0.0", "mRunning", "Bool", "运行标志")
    p.add_network(1, "启动逻辑", "code", "注释")
    return p


class TestExportSCL:
    @pytest.mark.parametrize("case", EXPORT_SCL, ids=[c["id"] for c in EXPORT_SCL])
    def test_scl_content(self, case):
        scl = generate_scl(_motor_program())
        for keyword in case["must_contain_in_export"]:
            assert keyword in scl, f"SCL 缺少 '{keyword}'"


class TestExportXML:
    @pytest.mark.parametrize("case", EXPORT_XML, ids=[c["id"] for c in EXPORT_XML])
    def test_xml_content(self, case):
        xml = generate_xml(_motor_program())
        for keyword in case["must_contain_in_export"]:
            assert keyword in xml, f"XML 缺少 '{keyword}'"

    def test_xml_parseable(self):
        import xml.etree.ElementTree as ET
        xml = generate_xml(_motor_program())
        root = ET.fromstring(xml)
        assert root is not None


class TestExportCSV:
    @pytest.mark.parametrize("case", EXPORT_CSV, ids=[c["id"] for c in EXPORT_CSV])
    def test_csv_content(self, case):
        csv = generate_tag_csv(_motor_program())
        for keyword in case["must_contain_in_export"]:
            assert keyword in csv, f"CSV 缺少 '{keyword}'"


class TestExportHMI:
    @pytest.mark.parametrize("case", EXPORT_HMI, ids=[c["id"] for c in EXPORT_HMI])
    def test_hmi_content(self, case):
        hmi = generate_hmi_tags(_motor_program())
        for keyword in case["must_contain_in_export"]:
            assert keyword in hmi, f"HMI 缺少 '{keyword}'"


class TestExportAlarm:
    @pytest.mark.parametrize("case", EXPORT_ALARM, ids=[c["id"] for c in EXPORT_ALARM])
    def test_alarm_detection(self, case):
        p = _make_program_from_vars(case["alarm_variables"])
        alarm_csv = generate_alarm_list(p)
        for name in case["must_detect"]:
            assert name in alarm_csv, f"应检测到报警变量 '{name}'"
        for name in case["must_not_detect"]:
            assert name not in alarm_csv, f"不应检测到非报警变量 '{name}'"


class TestExportJSON:
    @pytest.mark.parametrize("case", EXPORT_JSON, ids=[c["id"] for c in EXPORT_JSON])
    def test_json_summary(self, case):
        p = LadderProgram("Test", "")
        p.add_variable("I0.0", "bInput1", "Bool", "")
        p.add_variable("I0.1", "bInput2", "Bool", "")
        p.add_variable("Q0.0", "qOutput", "Bool", "")
        p.add_variable("M0.0", "mFlag", "Bool", "")
        data = json.loads(generate_variable_json(p))
        expected = case["expected_summary"]
        assert data["summary"]["total"] == expected["total"]
        assert data["summary"]["inputs"] == expected["inputs"]
        assert data["summary"]["outputs"] == expected["outputs"]
        assert data["summary"]["memory"] == expected["memory"]


# ---- API 端到端回归 ----

class TestAPIGolden:
    def test_ladder_generation(self, client):
        """API /generate/ladder — 结构化输出验证"""
        case = next(c for c in API_CASES if c["id"] == "api-ladder-motor")
        res = client.post(case["endpoint"], json={
            "input": case["input"],
            "model_id": "deepseek",
        })
        assert res.status_code == 200
        data = res.json()
        for key in case["must_contain_in_response"]:
            assert key in data, f"响应缺少 '{key}'"
        assert len(data["structured"].get("networks", [])) >= case["structured_min_networks"]

    def test_export_scl_api(self, client):
        """API /generate/export — SCL 导出验证"""
        case = next(c for c in API_CASES if c["id"] == "api-export-scl")
        res = client.post("/api/generate/export", json=case["export_payload"])
        assert res.status_code == 200
        content = res.json()["content"]
        for keyword in case["must_contain_in_content"]:
            assert keyword in content, f"SCL 导出缺少 '{keyword}'"
