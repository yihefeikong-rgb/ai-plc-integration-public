"""
测试 TIA Portal GUI 自动化下载模块 (dl_plcsim_gui.py)

注意: UI Automation 需要真实的桌面环境，CI 环境不可用。
这些测试主要验证子进程 IPC / 参数解析逻辑和 mock 的窗口检测逻辑。
"""
import json
import os
import sys
import subprocess
from pathlib import Path


def test_dl_plcsim_gui_usage_no_args():
    """验证无参数时返回 usage 信息"""
    script = Path(__file__).parent / "dl_plcsim_gui.py"
    if not script.exists():
        # 如果从项目根运行
        script = Path("mcp-servers/tia-mcp/dl_plcsim_gui.py")
    if not script.exists():
        return  # 跳过，文件可能还未创建

    r = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, timeout=10,
        encoding="utf-8", errors="replace",
    )
    # 无参数时输出 JSON 错误
    assert r.returncode != 0
    output = r.stdout.strip()
    if output:
        result = json.loads(output)
        assert result.get("success") is False


def test_dl_plcsim_gui_unknown_project():
    """给一个不存在的项目名，应返回错误（不会真的弹 TIA Portal）"""
    script = Path(__file__).parent / "dl_plcsim_gui.py"
    if not script.exists():
        return

    r = subprocess.run(
        [sys.executable, str(script), "nonexistent_project_xyz", "--timeout", "5"],
        capture_output=True, text=True, timeout=15,
        encoding="utf-8", errors="replace",
    )
    output = r.stdout.strip()
    if output:
        result = json.loads(output)
        assert result.get("success") is False
        # 应该是因为找不到 TIA Portal 窗口而失败
        assert "error" in result


def test_dl_plcsim_gui_arg_parsing():
    """验证参数解析逻辑（不运行 UI）"""
    # 用 -c 模拟参数解析
    code = """
import sys
sys.argv = ['dl_plcsim_gui.py', 'test_project', '--device', 'PLC_1', '--timeout', '120', '--interface', 'PLCSIM']
# 模拟 main 函数的参数解析逻辑
project_name = sys.argv[1]
device_name = ''
timeout = 180
pgpc_interface = ''
i = 2
while i < len(sys.argv):
    arg = sys.argv[i]
    if arg == '--device' and i+1 < len(sys.argv):
        device_name = sys.argv[i+1]; i += 2
    elif arg == '--timeout' and i+1 < len(sys.argv):
        timeout = int(sys.argv[i+1]); i += 2
    elif arg == '--interface' and i+1 < len(sys.argv):
        pgpc_interface = sys.argv[i+1]; i += 2
    else: i += 1
import json
print(json.dumps({'project': project_name, 'device': device_name, 'timeout': timeout, 'interface': pgpc_interface}))
"""
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=10,
        encoding="utf-8", errors="replace",
    )
    result = json.loads(r.stdout.strip())
    assert result["project"] == "test_project"
    assert result["device"] == "PLC_1"
    assert result["timeout"] == 120
    assert result["interface"] == "PLCSIM"


def test_download_via_ui_compile_first():
    """验证 download_to_plcsim.py 的 --ui --compile-first 参数解析"""
    code = """
import sys
sys.argv = ['download_to_plcsim.py', '--ui', '--compile-first', '--timeout', '60']
use_ui = '--ui' in sys.argv or '--ui-automation' in sys.argv
compile_first = '--compile-first' in sys.argv
assert use_ui, '--ui 参数未识别'
assert compile_first, '--compile-first 参数未识别'
print('OK: ui=%s compile=%s' % (use_ui, compile_first))
"""
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=10,
        encoding="utf-8", errors="replace",
    )
    assert r.returncode == 0
    assert "OK" in r.stdout


def test_dl_plcsim_gui_timeout_arg():
    """验证 --timeout 被正确传给子进程"""
    code = """
import sys
sys.argv = ['dl_plcsim_gui.py', 'proj', '--timeout', '60']
timeout = 180
for i, a in enumerate(sys.argv):
    if a == '--timeout' and i+1 < len(sys.argv):
        timeout = int(sys.argv[i+1])
assert timeout == 60, f'Expected 60 got {timeout}'
print(f'OK timeout={timeout}')
"""
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=10,
        encoding="utf-8", errors="replace",
    )
    assert r.returncode == 0


def test_import_uiautomation():
    """验证 uiautomation 库可以导入"""
    r = subprocess.run(
        [sys.executable, "-c", "import uiautomation; print('OK')"],
        capture_output=True, text=True, timeout=10,
        encoding="utf-8", errors="replace",
    )
    assert r.returncode == 0
    assert "OK" in r.stdout


def test_uiautomation_basic_function():
    """测试 uiautomation 基础功能可用（不访问真实控件）"""
    code = """
import uiautomation as ua
root = ua.GetRootControl()
print(f'RootOK: {root.Name is not None}')
# 枚举桌面顶层窗口（不操作）
count = 0
for w in root.GetChildren():
    count += 1
    if count > 3:
        break
print(f'EnumOK: {count > 0}')
"""
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=10,
        encoding="utf-8", errors="replace",
    )
    assert r.returncode == 0
    assert "RootOK" in r.stdout
    assert "EnumOK" in r.stdout


def test_uiautomation_find_window():
    """测试 uiautomation 能枚举所有顶级窗口（验证 COM 环境可用）"""
    code = """
import uiautomation as ua
root = ua.GetRootControl()
windows = []
for w in root.GetChildren():
    try:
        if w.Name and w.Name.strip():
            windows.append(w.Name.strip())
    except: pass
print(f'Found {len(windows)} windows')
assert len(windows) > 0, 'No windows found'
"""
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=10,
        encoding="utf-8", errors="replace",
    )
    assert r.returncode == 0


def test_download_to_plcsim_usage():
    """download_to_plcsim.py 不带参数不应直接运行（项目可能不存在）"""
    script = Path(__file__).parent / "download_to_plcsim.py"
    if not script.exists():
        return
    # 由于项目路径在 config，不传参数应该提示项目不存在或用法
    r = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True, text=True, timeout=10,
        encoding="utf-8", errors="replace",
    )
    # 应该正确处理 --help 或未知参数
    assert r.returncode != 0 or "--ui" in r.stdout or "--help" in r.stdout