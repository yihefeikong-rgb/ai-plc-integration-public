"""统一测试配置 — 共享 fixtures 和路径设置"""
import os
import sys
from pathlib import Path

import pytest

# 离线测试所需的环境变量（在任何被测模块 import 之前注入）。
# 一律 setdefault：测试可通过 monkeypatch 覆盖，本机 .env 加载的真实值优先。
_TEST_ENV_DEFAULTS = {
    "MCP_AUTH_TOKEN": "pytest-mcp-auth-token",
    "SAFETY_CONFIRMATION_SECRET": "pytest-confirmation-secret",
    "AUDIT_HMAC_KEY": "pytest-audit-hmac-key",
    "DEEPSEEK_API_KEY": "pytest-deepseek-key",
    "AI_PLC_OFFLINE_TESTING": "1",
}
for _key, _value in _TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(_key, _value)

# 确保项目各子模块在 sys.path 中
PROJECT_ROOT = Path(__file__).parent.parent
_paths_to_add = [
    str(PROJECT_ROOT),
    str(PROJECT_ROOT / "mcp-servers" / "plc-mcp-bridge"),
    str(PROJECT_ROOT / "mcp-servers" / "tia-mcp"),
    str(PROJECT_ROOT / "safety"),
    str(PROJECT_ROOT / "mcp_common"),
    str(PROJECT_ROOT / "edge-gateway" / "src"),
]
for p in _paths_to_add:
    if p not in sys.path:
        sys.path.append(p)


@pytest.fixture
def project_root():
    """返回项目根目录 Path"""
    return PROJECT_ROOT
