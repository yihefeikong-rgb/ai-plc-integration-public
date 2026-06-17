"""API 测试 — /api/prompts CRUD"""


class TestPrompts:
    def test_list_default_templates(self, client):
        res = client.get("/api/prompts")
        assert res.status_code == 200
        data = res.json()
        assert "templates" in data
        assert data["total"] >= 9  # 9 个内置模板

    def test_list_categories(self, client):
        res = client.get("/api/prompts/categories")
        assert res.status_code == 200
        data = res.json()
        assert "categories" in data
        names = [c["name"] for c in data["categories"]]
        assert "顺序控制" in names

    def test_get_template(self, client):
        res = client.get("/api/prompts/traffic-light")
        assert res.status_code == 200
        t = res.json()["template"]
        assert t["id"] == "traffic-light"
        assert "variables" in t
        assert len(t["variables"]) >= 1

    def test_get_not_found(self, client):
        res = client.get("/api/prompts/nonexistent")
        assert res.status_code == 404

    def test_create_template(self, client):
        import uuid
        name = f"TestTpl_{uuid.uuid4().hex[:6]}"
        res = client.post("/api/prompts", json={
            "name": name,
            "category": "测试",
            "description": "测试模板",
            "content": "你好 {name}",
            "variables": [{"name": "name", "label": "名称", "default": "世界", "type": "string"}],
        })
        assert res.status_code == 201
        assert res.json()["template"]["name"] == name
        # 清理
        tid = res.json()["template"]["id"]
        client.delete(f"/api/prompts/{tid}")

    def test_update_template(self, client):
        import uuid
        name = f"UpdTpl_{uuid.uuid4().hex[:6]}"
        res = client.post("/api/prompts", json={"name": name, "category": "测试"})
        tid = res.json()["template"]["id"]
        # 更新
        res = client.put(f"/api/prompts/{tid}", json={"description": "updated"})
        assert res.status_code == 200
        assert res.json()["template"]["description"] == "updated"
        client.delete(f"/api/prompts/{tid}")

    def test_delete_template(self, client):
        import uuid
        name = f"DelTpl_{uuid.uuid4().hex[:6]}"
        res = client.post("/api/prompts", json={"name": name, "category": "测试"})
        tid = res.json()["template"]["id"]
        res = client.delete(f"/api/prompts/{tid}")
        assert res.status_code == 200

    def test_filter_by_category(self, client):
        res = client.get("/api/prompts?category=顺序控制")
        assert res.status_code == 200
        for t in res.json()["templates"]:
            assert t["category"] == "顺序控制"
