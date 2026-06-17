"""API 测试 — /api/generate (mock LLM)"""


class TestGenerateLadder:
    def test_generate_ladder(self, client):
        """梯形图生成 — 应使用 mock LLM 返回结构化数据"""
        res = client.post("/api/generate/ladder", json={
            "input": "生成电机启动停止控制程序",
            "model_id": "deepseek",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["title"] != ""
        assert "structured" in data
        assert data["mode"] in ("llm", "demo", "placeholder")

    def test_generate_empty_input(self, client):
        res = client.post("/api/generate/ladder", json={"input": ""})
        assert res.status_code == 400

    def test_generate_scl(self, client):
        res = client.post("/api/generate/ladder/scl", json={
            "input": "电机控制",
        })
        assert res.status_code == 200
        data = res.json()
        assert "scl" in data

    def test_generate_xml(self, client):
        res = client.post("/api/generate/ladder/xml", json={
            "input": "电机控制",
        })
        assert res.status_code == 200
        data = res.json()
        assert "xml" in data


class TestExport:
    def test_export_scl(self, client):
        res = client.post("/api/generate/export", json={
            "title": "Test",
            "description": "Test block",
            "variables": [{"address": "I0.0", "name": "bStart", "data_type": "Bool", "comment": "启动"}],
            "networks": [{"number": 1, "title": "Net1", "code": "code", "comment": "comment"}],
            "format": "scl",
            "block_type": "FB",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["format"] == "scl"
        assert "FUNCTION_BLOCK" in data["content"]

    def test_export_csv(self, client):
        res = client.post("/api/generate/export", json={
            "title": "Test",
            "variables": [{"address": "I0.0", "name": "bStart", "data_type": "Bool", "comment": ""}],
            "networks": [],
            "format": "csv",
        })
        assert res.status_code == 200
        assert "bStart" in res.json()["content"]

    def test_export_json(self, client):
        res = client.post("/api/generate/export", json={
            "title": "Test",
            "variables": [{"address": "I0.0", "name": "bStart", "data_type": "Bool", "comment": ""}],
            "networks": [],
            "format": "json",
        })
        assert res.status_code == 200
        assert res.json()["format"] == "json"

    def test_export_invalid_format(self, client):
        res = client.post("/api/generate/export", json={
            "title": "Test",
            "variables": [],
            "networks": [],
            "format": "invalid",
        })
        assert res.status_code == 400


class TestPromptDebug:
    def test_get_prompt(self, client):
        res = client.post("/api/generate/prompt", json={
            "input": "电机控制",
        })
        assert res.status_code == 200
        assert "prompt" in res.json()
