"""API 测试 — /api/models"""


class TestModels:
    def test_list_models(self, client):
        res = client.get("/api/models")
        assert res.status_code == 200
        data = res.json()
        assert "models" in data
        assert len(data["models"]) >= 1
        # DeepSeek 应在列表中
        ids = [m["id"] for m in data["models"]]
        assert "deepseek" in ids

    def test_get_model(self, client):
        res = client.get("/api/models/deepseek")
        assert res.status_code == 200
        data = res.json()
        assert data["model"]["id"] == "deepseek"

    def test_get_model_not_found(self, client):
        res = client.get("/api/models/nonexistent")
        assert res.status_code == 404

    def test_list_and_get_require_local_session(self, client):
        """模型列表泄露已配置哪些 LLM 供应商，必须有会话令牌。"""
        res = client.get("/api/models", headers={"X-Local-Api-Token": "wrong-token"})
        assert res.status_code == 401
        res = client.get("/api/models/deepseek", headers={"X-Local-Api-Token": "wrong-token"})
        assert res.status_code == 401
