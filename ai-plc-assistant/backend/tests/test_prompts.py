"""Prompt 模板 CRUD API 测试"""


class TestListPrompts:
    """GET /api/prompts — 模板列表"""

    def test_list_returns_array(self, client):
        """应返回模板列表（字段名为 templates）"""
        resp = client.get("/api/prompts")
        assert resp.status_code == 200
        data = resp.json()
        assert "templates" in data
        assert isinstance(data["templates"], list)

    def test_list_contains_prompts(self, client, sample_prompts):
        """列表应包含测试用的模板"""
        resp = client.get("/api/prompts")
        data = resp.json()
        names = [p["name"] for p in data["templates"]]
        assert "电机控制" in names
        assert "交通灯控制" in names

    def test_list_returns_metadata(self, client):
        """每个模板含基本元数据"""
        resp = client.get("/api/prompts")
        for p in resp.json()["templates"]:
            assert "id" in p
            assert "name" in p
            assert "category" in p
            assert "description" in p


class TestGetPrompt:
    """GET /api/prompts/{id} — 模板详情"""

    def test_get_by_id(self, client, sample_prompts):
        """按 ID 获取模板详情"""
        resp = client.get("/api/prompts/motor-control")
        assert resp.status_code == 200
        data = resp.json()
        assert "template" in data
        assert data["template"]["name"] == "电机控制"
        assert "content" in data["template"]

    def test_404_for_nonexistent(self, client):
        """不存在的 ID 应返回 404"""
        resp = client.get("/api/prompts/nonexistent-id-12345")
        assert resp.status_code == 404


class TestCreatePrompt:
    """POST /api/prompts — 创建模板"""

    def test_create_valid(self, client, sample_prompts):
        """创建有效模板"""
        resp = client.post("/api/prompts", json={
            "name": "新测试模板",
            "category": "测试类别",
            "description": "测试用",
            "content": "请生成测试程序。",
            "variables": [],
        })
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert "template" in data
        assert data["template"]["name"] == "新测试模板"

    def test_create_requires_name(self, client, sample_prompts):
        """缺少名称应返回错误"""
        resp = client.post("/api/prompts", json={
            "category": "测试",
            "content": "test",
        })
        assert resp.status_code in (400, 422)

    def test_create_requires_content(self, client, sample_prompts):
        """缺少内容应返回错误"""
        resp = client.post("/api/prompts", json={
            "name": "测试",
            "content": "",
        })
        assert resp.status_code in (400, 422)


class TestUpdatePrompt:
    """PUT /api/prompts/{id} — 更新模板"""

    def test_update_name(self, client, sample_prompts):
        """更新模板名称"""
        resp = client.put("/api/prompts/motor-control", json={
            "name": "电机控制(已更新)",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "template" in data
        assert data["template"]["name"] == "电机控制(已更新)"

    def test_update_404(self, client):
        """更新不存在的模板应返回 404"""
        resp = client.put("/api/prompts/nonexistent", json={"name": "新名称"})
        assert resp.status_code == 404


class TestDeletePrompt:
    """DELETE /api/prompts/{id} — 删除模板"""

    def test_delete_existing(self, client, sample_prompts):
        """删除存在的模板"""
        resp = client.delete("/api/prompts/traffic-light")
        assert resp.status_code == 200
        # 验证已删除
        resp2 = client.get("/api/prompts/traffic-light")
        assert resp2.status_code == 404

    def test_delete_404(self, client):
        """删除不存在的模板应返回 404"""
        resp = client.delete("/api/prompts/nonexistent")
        assert resp.status_code == 404


class TestPromptCategories:
    """GET /api/prompts/categories — 分类列表"""

    def test_categories_returns_list(self, client, sample_prompts):
        """应返回分类列表"""
        resp = client.get("/api/prompts/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert isinstance(data["categories"], list)
        names = [c["name"] for c in data["categories"]]
        assert "运动控制" in names
        assert "顺序控制" in names
