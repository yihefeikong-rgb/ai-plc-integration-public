"""梯形图/SCL/XML 生成 API 测试"""

import json
import pytest


class TestGenerateLadder:
    """POST /api/generate/ladder — 自然语言 → 梯形图"""

    def test_basic_generate(self, client):
        """基本梯形图生成"""
        resp = client.post("/api/generate/ladder", json={
            "input": "电机启动停止控制"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"]
        assert data["structured"]
        assert data["mode"] == "llm"
        assert "variables" in data["structured"]
        assert "networks" in data["structured"]

    def test_empty_input_rejected(self, client):
        """空输入应返回 400"""
        resp = client.post("/api/generate/ladder", json={"input": ""})
        assert resp.status_code == 400

    def test_structured_has_correct_shape(self, client):
        """返回的 structured 应有正确的数据结构"""
        resp = client.post("/api/generate/ladder", json={
            "input": "交通灯控制，东西和南北方向交替通行"
        })
        data = resp.json()
        s = data["structured"]
        assert "title" in s
        assert "description" in s
        assert isinstance(s["variables"], list)
        assert isinstance(s["networks"], list)
        if s["networks"]:
            n = s["networks"][0]
            assert "number" in n
            assert "title" in n
            assert "rungs" in n or "code" in n

    def test_with_template_id(self, client):
        """支持 template_id 参数"""
        resp = client.post("/api/generate/ladder", json={
            "input": "电机控制",
            "template_id": "motor-start-stop",
        })
        assert resp.status_code == 200

    def test_with_variables(self, client):
        """支持传入变量"""
        resp = client.post("/api/generate/ladder", json={
            "input": "交通灯控制",
            "variables": {"green_time": "45"},
        })
        assert resp.status_code == 200


class TestGenerateSCL:
    """POST /api/generate/ladder/scl — 自然语言 → SCL"""

    def test_basic_scl(self, client):
        """基本 SCL 生成"""
        resp = client.post("/api/generate/ladder/scl", json={
            "input": "电机正反转控制，有互锁"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "scl" in data
        assert data["mode"] == "llm"

    def test_scl_contains_code(self, client):
        """SCL 应包含代码内容"""
        resp = client.post("/api/generate/ladder/scl", json={
            "input": "电机启停"
        })
        data = resp.json()
        assert len(data["scl"]) > 10  # 至少有代码内容

    def test_empty_input_rejected(self, client):
        """空输入应返回 400"""
        resp = client.post("/api/generate/ladder/scl", json={"input": ""})
        assert resp.status_code == 400


class TestGenerateXML:
    """POST /api/generate/ladder/xml — 自然语言 → PLCopen XML"""

    def test_basic_xml(self, client):
        """基本 XML 生成"""
        resp = client.post("/api/generate/ladder/xml", json={
            "input": "电机启动停止"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "xml" in data
        assert data["mode"] == "llm"

    def test_xml_is_valid_xml(self, client):
        """生成的 XML 应包含 PLCopen 标记"""
        resp = client.post("/api/generate/ladder/xml", json={
            "input": "电机启停"
        })
        data = resp.json()
        xml = data["xml"]
        assert "<?xml" in xml or "<PLCopen" in xml or "<Project" in xml


class TestExport:
    """POST /api/generate/export — 结构化数据 → 多格式导出"""

    @pytest.fixture
    def sample_structured(self):
        return {
            "title": "TestMotor",
            "description": "电机测试",
            "variables": [
                {"address": "I0.0", "name": "bStart", "data_type": "Bool", "comment": "启动"},
                {"address": "Q0.0", "name": "qMotor", "data_type": "Bool", "comment": "电机"},
            ],
            "networks": [
                {"number": 1, "title": "启停", "code": "bStart --| |-- qMotor --( )--", "comment": "自锁"},
            ],
        }

    def test_export_scl(self, client, sample_structured):
        """导出 SCL 格式"""
        resp = client.post("/api/generate/export", json={
            **sample_structured,
            "format": "scl",
            "block_type": "FB",
            "block_name": "TestMotor",
        })
        assert resp.status_code == 200
        assert "content" in resp.json()

    def test_export_xml(self, client, sample_structured):
        """导出 XML 格式"""
        resp = client.post("/api/generate/export", json={
            **sample_structured,
            "format": "xml",
        })
        assert resp.status_code == 200

    def test_export_csv(self, client, sample_structured):
        """导出 CSV 标签表"""
        resp = client.post("/api/generate/export", json={
            **sample_structured,
            "format": "csv",
        })
        assert resp.status_code == 200

    def test_export_hmi(self, client, sample_structured):
        """导出 HMI 标签"""
        resp = client.post("/api/generate/export", json={
            **sample_structured,
            "format": "hmi",
        })
        assert resp.status_code == 200

    def test_export_json(self, client, sample_structured):
        """导出 JSON 变量列表"""
        resp = client.post("/api/generate/export", json={
            **sample_structured,
            "format": "json",
        })
        assert resp.status_code == 200

    def test_export_invalid_format(self, client, sample_structured):
        """不支持的格式应返回 400"""
        resp = client.post("/api/generate/export", json={
            **sample_structured,
            "format": "invalid_format_xxx",
        })
        assert resp.status_code == 400


class TestGeneratePrompt:
    """POST /api/generate/prompt — 调试 Prompt"""

    def test_basic_prompt(self, client):
        """基本 Prompt 生成"""
        resp = client.post("/api/generate/prompt", json={
            "input": "电机控制"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "prompt" in data
        assert "电机" in data["prompt"] or "Motor" in data["prompt"] or "LAD" in data["prompt"]

    def test_empty_input_rejected(self, client):
        """空输入应返回 400"""
        resp = client.post("/api/generate/prompt", json={"input": ""})
        assert resp.status_code == 400

    def test_prompt_contains_ladder_instructions(self, client):
        """Prompt 应包含梯形图生成指令"""
        resp = client.post("/api/generate/prompt", json={
            "input": "交通灯"
        })
        data = resp.json()
        prompt = data["prompt"]
        assert "Network" in prompt or "梯形图" in prompt or "变量表" in prompt
