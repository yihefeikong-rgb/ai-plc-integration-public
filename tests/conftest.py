"""统一测试配置 — 共享 fixtures 和路径设置"""
import sys
from pathlib import Path

import pytest

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
