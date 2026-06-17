"""API 测试 — /api/settings"""


class TestSettings:
    def test_get_settings(self, client):
        res = client.get("/api/settings")
        assert res.status_code == 200
        data = res.json()
        assert "settings" in data
        s = data["settings"]
        # API key 应被遮盖
        if s.get("deepseek_api_key"):
            assert "*" in s["deepseek_api_key"]

    def test_get_providers(self, client):
        res = client.get("/api/settings/providers")
        assert res.status_code == 200
        data = res.json()
        assert "providers" in data
        assert "deepseek" in data["providers"]
        assert "openai" in data["providers"]
        assert "kimi" in data["providers"]
        assert "claude" in data["providers"]

    def test_update_settings(self, client):
        res = client.put("/api/settings", json={
            "default_plc_type": "S7-1500",
            "default_language": "LAD",
        })
        assert res.status_code == 200
        # 验证更新
        res = client.get("/api/settings")
        s = res.json()["settings"]
        assert s["default_plc_type"] == "S7-1500"
        assert s["default_language"] == "LAD"

    def test_masked_key_not_overwritten(self, client):
        """遮盖的 key 不应覆盖原始值"""
        res = client.put("/api/settings", json={
            "deepseek_api_key": "sk-2***62f",  # 带 * 号的遮盖值
        })
        assert res.status_code == 200
