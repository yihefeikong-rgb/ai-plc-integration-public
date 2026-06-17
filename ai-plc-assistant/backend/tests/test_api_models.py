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
