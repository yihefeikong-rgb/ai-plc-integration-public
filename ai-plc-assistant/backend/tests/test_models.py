"""模型列表 API 测试"""


class TestModels:
    """GET /api/models — 模型列表"""

    def test_list_models(self, client):
        """应返回模型列表"""
        resp = client.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert isinstance(data["models"], list)

    def test_models_have_required_fields(self, client):
        """每个模型应包含基本字段 (id, name, enabled)"""
        resp = client.get("/api/models")
        for m in resp.json()["models"]:
            assert "id" in m
            assert "name" in m
            assert "enabled" in m

    def test_contains_deepseek(self, client):
        """默认应包含 DeepSeek"""
        resp = client.get("/api/models")
        ids = [m["id"] for m in resp.json()["models"]]
        assert "deepseek" in ids


class TestModelDetail:
    """GET /api/models/{id} — 模型详情"""

    def test_get_existing(self, client):
        """获取存在的模型详情"""
        resp = client.get("/api/models/deepseek")
        assert resp.status_code == 200
        data = resp.json()
        assert "model" in data
        assert data["model"]["id"] == "deepseek"

    def test_get_nonexistent(self, client):
        """不存在的模型应返回 404"""
        resp = client.get("/api/models/nonexistent_model_xyz")
        assert resp.status_code == 404
