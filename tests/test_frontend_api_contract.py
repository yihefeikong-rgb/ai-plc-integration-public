import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_MODULE = PROJECT_ROOT / "ai-plc-assistant" / "frontend" / "src" / "api.js"

# 匹配注释与字符串字面量（含模板字符串）：统计真实 fetch( 调用前先剔除它们，
# 避免注释或字符串里出现字面 "fetch(" 时破坏契约计数（过度耦合实现细节）
_STRINGS_AND_COMMENTS = re.compile(
    r'/\*.*?\*/|//[^\r\n]*|`(?:\\.|[^`\\])*`|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
    re.DOTALL,
)


def _count_fetch_calls(content: str) -> int:
    """统计源码中真实出现的 fetch( 调用（排除注释与字符串字面量）。"""
    return _STRINGS_AND_COMMENTS.sub("", content).count("fetch(")


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
    # 仅允许两处真实 fetch(：request() 助手内的统一出口与 streamChat 的 SSE 出口；
    # 统计前剔除注释与字符串字面量，避免对实现细节（如注释中的 "fetch("）过度耦合
    assert _count_fetch_calls(content) == 2
