"""
pytest 全局配置 — 路径注册 + 测试分类标记 + 硬件依赖检测
"""

import os
import sys
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "mcp-servers", "tia-mcp"))


def pytest_configure(config):
    """注册自定义标记，消除 pytest 警告"""
    config.addinivalue_line("markers", "plcsim: 需要 PLCSIM Advanced Runtime")
    config.addinivalue_line("markers", "tia: 需要 TIA Portal 安装")
    config.addinivalue_line("markers", "hardware: 需要真实 PLC/机器人硬件")
    config.addinivalue_line("markers", "desktop: 需要桌面环境 (COM/UI Automation)")
    config.addinivalue_line("markers", "manual: 人工验收脚本，不自动运行")
    config.addinivalue_line("markers", "asyncio: 异步测试")


def pytest_collection_modifyitems(config, items):
    """自动跳过硬件/桌面依赖的测试（环境变量未设置时）"""
    skip_plcsim = pytest.mark.skipif(
        not os.environ.get("PLCSIM_AVAILABLE"),
        reason="需要 PLCSIM Advanced Runtime (设置 PLCSIM_AVAILABLE=1)"
    )
    skip_tia = pytest.mark.skipif(
        not os.environ.get("TIA_PORTAL_AVAILABLE"),
        reason="需要 TIA Portal (设置 TIA_PORTAL_AVAILABLE=1)"
    )
    skip_desktop = pytest.mark.skipif(
        not os.environ.get("DESKTOP_SESSION") and not os.environ.get("DISPLAY"),
        reason="需要桌面环境 (COM/UI Automation)"
    )

    for item in items:
        if item.get_closest_marker("plcsim"):
            item.add_marker(skip_plcsim)
        if item.get_closest_marker("tia"):
            item.add_marker(skip_tia)
        if item.get_closest_marker("desktop"):
            item.add_marker(skip_desktop)
