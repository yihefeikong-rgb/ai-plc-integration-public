"""API 测试 — /api/projects CRUD"""


class TestProjects:
    def test_list_empty(self, client):
        res = client.get("/api/projects")
        assert res.status_code == 200
        assert res.json()["projects"] == []

    def test_create_project(self, client):
        res = client.post("/api/projects", json={
            "name": "TestProject",
            "plc_type": "S7-1200",
            "tia_version": "V18",
            "language": "SCL",
        })
        assert res.status_code == 201
        data = res.json()
        assert data["project"]["name"] == "TestProject"
        assert data["project"]["plc_type"] == "S7-1200"
        assert data["project"]["id"]  # 应有 UUID

    def test_crud_flow(self, client):
        # Create
        res = client.post("/api/projects", json={"name": "CRUD Test"})
        assert res.status_code == 201
        pid = res.json()["project"]["id"]

        # Read
        res = client.get(f"/api/projects/{pid}")
        assert res.status_code == 200
        assert res.json()["project"]["name"] == "CRUD Test"

        # Update
        res = client.put(f"/api/projects/{pid}", json={"name": "Updated"})
        assert res.status_code == 200
        assert res.json()["project"]["name"] == "Updated"

        # Delete
        res = client.delete(f"/api/projects/{pid}")
        assert res.status_code == 200

        # Verify deleted
        res = client.get(f"/api/projects/{pid}")
        assert res.status_code == 404

    def test_get_not_found(self, client):
        res = client.get("/api/projects/nonexistent-id")
        assert res.status_code == 404

    def test_list_after_create(self, client):
        res = client.get("/api/projects")
        before_count = len(res.json()["projects"])

        client.post("/api/projects", json={"name": "P1"})
        client.post("/api/projects", json={"name": "P2"})

        res = client.get("/api/projects")
        after = res.json()["projects"]
        after_names = {p["name"] for p in after}

        assert res.status_code == 200
        assert "P1" in after_names
        assert "P2" in after_names
        assert len(after) >= before_count + 2
