"""统一测试配置 — 共享 fixtures 和路径设置"""
import os
import sys
from pathlib import Path

import pytest

# 离线测试所需的环境变量（在任何被测模块 import 之前注入）。
# 一律强制覆盖（而非 setdefault）：测试进程内必须使用固定测试值，
# 开发环境 .env 加载的真实凭据不得进入测试进程/日志/输出，与
# ai-plc-assistant/backend/tests/conftest.py 的隔离策略保持一致（fail-closed）。
# 测试内仍可通过 monkeypatch.setenv 覆盖。
_TEST_ENV_DEFAULTS = {
    "MCP_AUTH_TOKEN": "pytest-mcp-auth-token",
    "SAFETY_CONFIRMATION_SECRET": "pytest-confirmation-secret",
    "AUDIT_HMAC_KEY": "pytest-audit-hmac-key",
    "DEEPSEEK_API_KEY": "pytest-deepseek-key",
    "AI_PLC_OFFLINE_TESTING": "1",
    # tia-mcp 工程态操作确认门的显式 opt-in 降级：测试模拟自动化流程的
    # 已配置降级场景（生产默认不设置此变量，保持 fail-closed 强制确认）。
    "TIA_MCP_ALLOW_UNCONFIRMED_ENGINEERING": "1",
}
os.environ.update(_TEST_ENV_DEFAULTS)

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
