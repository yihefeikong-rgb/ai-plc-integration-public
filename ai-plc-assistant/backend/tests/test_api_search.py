"""API 测试 — /api/search"""


class TestSearch:
    def test_search_empty_query(self, client):
        res = client.get("/api/search?q=")
        assert res.status_code == 200
        assert res.json()["results"] == []

    def test_search_no_index(self, client):
        res = client.get("/api/search?q=motor")
        assert res.status_code == 200
        assert res.json()["total"] == 0

    def test_search_types(self, client):
        res = client.get("/api/search/types")
        assert res.status_code == 200
        assert "types" in res.json()

    def test_search_stats(self, client):
        res = client.get("/api/search/stats")
        assert res.status_code == 200
        data = res.json()
        assert "total_entries" in data

    def test_clear_index(self, client):
        res = client.delete("/api/search/index")
        assert res.status_code == 200
        assert res.json()["status"] == "cleared"
