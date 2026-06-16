"""plc-mcp-bridge 测试配置 — 统一路径和 fixtures"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# 确保 plc-mcp-bridge 源码目录在 path 中
BRIDGE_ROOT = Path(__file__).parent.parent
PROJECT_ROOT = BRIDGE_ROOT.parent.parent
_paths_to_add = [
    str(BRIDGE_ROOT),
    str(PROJECT_ROOT / "mcp-servers" / "tia-mcp"),
    str(PROJECT_ROOT / "safety"),
    str(PROJECT_ROOT / "mcp_common"),
]
for p in _paths_to_add:
    if p not in sys.path:
        sys.path.append(p)


@pytest.fixture
def mock_adapter(monkeypatch):
    """Mock S7 适配器，避免测试依赖真实 PLC"""
    mock = MagicMock()
    mock.is_connected = True
    mock.read_address.return_value = 0
    mock.write_address.return_value = "✅ 写入成功"
    monkeypatch.setattr("s7_adapter.adapter", mock)
    return mock


@pytest.fixture
def mock_tiaworker(monkeypatch):
    """Mock TiaWorker 子进程调用"""
    mock = MagicMock(return_value={"success": True, "data": {}})
    monkeypatch.setattr("_helpers._run_tiaworker", mock)
    return mock
