from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_MODULE = PROJECT_ROOT / "ai-plc-assistant" / "frontend" / "src" / "api.js"


def test_all_control_requests_use_the_shared_auth_and_error_boundary():
    """上传、生成和删除不能绕过本地控制令牌或把 HTTP 错误当成功。"""
    content = API_MODULE.read_text(encoding="utf-8")

    assert "const headers = { ...localControlHeaders(), ...options.headers }" in content
    assert "return request('/projects/import'" in content
    assert "return request('/knowledge/import'" in content
    assert "request(`/knowledge/documents/${id}`, { method: 'DELETE' })" in content
    assert "return request(url, { method: 'POST' })" in content
    assert "request('/generate/ladder'" in content
    assert "request('/generate/ladder/scl'" in content
    assert "request('/generate/export'" in content
    assert "headers: { ...localControlHeaders(), 'Content-Type': 'application/json' }" in content
    assert content.count("fetch(") == 2
