"""健康检查 API 测试"""

def test_health_endpoint(client):
    """GET /api/health 应返回 ok 状态"""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_health_returns_version(client):
    """健康检查应返回版本号"""
    resp = client.get("/api/health")
    data = resp.json()
    assert data["version"] == "1.0.0"
