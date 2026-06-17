"""API 测试 — /api/conversations CRUD + messages"""


class TestConversations:
    def test_list_empty(self, client):
        res = client.get("/api/conversations")
        assert res.status_code == 200
        assert res.json()["conversations"] == []

    def test_create_conversation(self, client):
        res = client.post("/api/conversations", json={
            "title": "Test Chat",
            "model_id": "deepseek",
        })
        assert res.status_code == 201
        conv = res.json()["conversation"]
        assert conv["title"] == "Test Chat"
        assert conv["model_id"] == "deepseek"
        assert "id" in conv

    def test_crud_flow(self, client):
        # Create
        res = client.post("/api/conversations", json={"title": "CRUD"})
        assert res.status_code == 201
        cid = res.json()["conversation"]["id"]

        # Read
        res = client.get(f"/api/conversations/{cid}")
        assert res.status_code == 200
        assert res.json()["conversation"]["title"] == "CRUD"

        # Update
        res = client.put(f"/api/conversations/{cid}", json={"title": "Updated"})
        assert res.status_code == 200

        # Add message
        res = client.post(f"/api/conversations/{cid}/messages", json={
            "role": "user",
            "content": "Hello",
        })
        assert res.status_code == 201
        assert res.json()["message"]["content"] == "Hello"

        # Read with messages
        res = client.get(f"/api/conversations/{cid}")
        msgs = res.json()["conversation"]["messages"]
        assert len(msgs) == 1
        assert msgs[0]["content"] == "Hello"

        # Delete
        res = client.delete(f"/api/conversations/{cid}")
        assert res.status_code == 200

        # Verify deleted
        res = client.get(f"/api/conversations/{cid}")
        assert res.status_code == 404

    def test_get_not_found(self, client):
        res = client.get("/api/conversations/nonexistent")
        assert res.status_code == 404

    def test_multiple_messages(self, client):
        res = client.post("/api/conversations", json={"title": "Multi"})
        cid = res.json()["conversation"]["id"]

        client.post(f"/api/conversations/{cid}/messages", json={"role": "user", "content": "Q1"})
        client.post(f"/api/conversations/{cid}/messages", json={"role": "assistant", "content": "A1"})
        client.post(f"/api/conversations/{cid}/messages", json={"role": "user", "content": "Q2"})

        res = client.get(f"/api/conversations/{cid}")
        msgs = res.json()["conversation"]["messages"]
        assert len(msgs) == 3
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
