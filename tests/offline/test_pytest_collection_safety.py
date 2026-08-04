"""默认 pytest 收集边界安全测试（fail-closed）。

验证根目录 pytest.ini 的默认收集范围不会触碰 PLC / 桌面 / 归档测试:

  1. addopts 的标记排除必须是完整的（integration/hardware/desktop/network）；
  2. testpaths 不得覆盖 mcp-servers/tia-mcp/archived（其中含 test_*.py，
     一旦被默认收集就会触发真实环境路径）；
  3. 定向动态收集受保护测试文件，确认标记过滤真实生效。

历史实现会对整库 tests+orchestrator/tests 执行 pytest --collect-only
（每次运行都启动全新解释器，耗时数秒且结果不缓存）。这里改为毫秒级
配置断言 + 仅对受保护文件做一次定向收集（lru_cache 会话内缓存）。
刻意不做跨会话磁盘缓存 —— 缓存过期会让测试"假绿"（fail-open），
违背本文件的安全边界职责。
"""
import configparser
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]

# 默认收集下必须被排除的受保护测试文件（全部带 hardware/desktop 标记）。
# 其中任何一个出现在默认收集结果里，都意味着默认 pytest 可能触碰 PLC / 桌面程序。
_PROTECTED_TEST_FILES = (
    "tests/test_download_flow.py",
    "tests/test_robot_mcp.py",
)
# 归档目录内含 test_*.py，默认收集一旦覆盖该目录即可能触碰真实环境。
_ARCHIVED_TESTS = "mcp-servers/tia-mcp/archived"
# 默认收集必须排除的动态操作标记（与 pytest.ini addopts 一一对应）。
_OFFLINE_EXCLUDED_MARKERS = ("integration", "hardware", "desktop", "network")


def _pytest_ini_section():
    parser = configparser.ConfigParser()
    ini_path = PROJECT_ROOT / "pytest.ini"
    parser.read(ini_path, encoding="utf-8")
    return parser["pytest"]


@lru_cache(maxsize=1)
def _protected_collection_result():
    """会话内只跑一次的定向收集：验证受保护文件在真实标记过滤下不被收集。"""
    env = os.environ | {"PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *_PROTECTED_TEST_FILES],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_default_collection_excludes_hardware_and_desktop_tests():
    pytest_ini = _pytest_ini_section()

    # 1) 静态：addopts 必须排除所有动态操作标记（fail-closed，毫秒级）。
    addopts = pytest_ini.get("addopts", "")
    for marker in _OFFLINE_EXCLUDED_MARKERS:
        assert f"not {marker}" in addopts, f"addopts 未排除标记 {marker}: {addopts}"

    # 2) 静态：testpaths 不得覆盖归档目录，归档 test_*.py 才能保持不被默认收集。
    testpaths = pytest_ini.get("testpaths", "")
    assert _ARCHIVED_TESTS not in testpaths, f"testpaths 覆盖了归档目录: {testpaths}"

    # 3) 动态：定向收集受保护文件，验证标记过滤真实生效（而非仅配置存在）。
    result = _protected_collection_result()
    # 退出码 5 = "no tests collected"：受保护文件全部被标记过滤后 0 个测试，
    # 这正是 fail-closed 的预期结果，与退出码 0（显式 -m 下无测试可跑）等价。
    assert result.returncode in (0, 5), result.stderr
    for path in _PROTECTED_TEST_FILES:
        assert path not in result.stdout, f"默认收集错误地包含了受保护测试: {path}"
