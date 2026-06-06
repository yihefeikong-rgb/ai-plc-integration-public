"""
启动 S7-PLCSIM Advanced V8.0 GUI 界面。

PLCSIM Advanced GUI (UserInterface.exe) 是仿真软件的主窗口。
启动它之后才能通过 API 创建/恢复实例并连接到 Factory I/O。

搜索路径优先级:
  1. config.yaml 中的 advanced_install_dir
  2. Start Menu 快捷方式（如果存在）
  3. Common Files 安装目录（默认 V8.0 API 路径）

用法:
  python scripts/start_plcsim_gui.py
"""
import os
import sys
import time
import subprocess
import ctypes

# ── 搜索路径 ──
_POTENTIAL_PATHS = []


def _add_unique(path):
    """添加路径到列表（去重）"""
    if path and os.path.exists(path) and path not in _POTENTIAL_PATHS:
        _POTENTIAL_PATHS.append(path)


def _find_ui_exe() -> str:
    """查找 PLCSIM Advanced UserInterface.exe"""
    # 1. 从 config.yaml 读取
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mcp-servers', 'tia-mcp'))
        from config_loader import cfg
        adv_dir = cfg.simulation.advanced_install_dir
        _add_unique(os.path.join(adv_dir, 'bin', 'Siemens.Simatic.PlcSim.Advanced.UserInterface.exe'))
    except Exception:
        pass

    # 2. 扫描 Start Menu 快捷方式
    shortcut_paths = [
        os.path.join(os.environ.get("ALLUSERSPROFILE", r"C:\ProgramData"),
                     "Microsoft", "Windows", "Start Menu", "Programs",
                     "Siemens Automation", "S7-PLCSIM Advanced V8.0.lnk"),
        os.path.join(os.environ.get("ALLUSERSPROFILE", r"C:\ProgramData"),
                     "Microsoft", "Windows", "Start Menu", "Programs",
                     "Siemens Automation", "S7-PLCSIM Advanced V5.0.lnk"),
    ]
    for sp in shortcut_paths:
        if os.path.exists(sp):
            try:
                r = subprocess.run(
                    ['powershell', '-Command',
                     f'$shell = New-Object -ComObject WScript.Shell; '
                     f'$link = $shell.CreateShortcut("{sp}"); '
                     f'echo $link.TargetPath'],
                    capture_output=True, text=True, timeout=5,
                )
                target = r.stdout.strip()
                if target and os.path.exists(target):
                    _add_unique(target)
            except Exception:
                pass

    # 3. 扫描 Common Files 下的 bin/
    fallback_dirs = [
        r"C:\Program Files\Siemens\PLCSIMADV",
        r"C:\Program Files (x86)\Siemens\PLCSIMADV",
    ]
    for d in fallback_dirs:
        candidate = os.path.join(d, 'bin', 'Siemens.Simatic.PlcSim.Advanced.UserInterface.exe')
        _add_unique(candidate)

    # 返回第一个找到的
    return _POTENTIAL_PATHS[0] if _POTENTIAL_PATHS else ""


def is_gui_running() -> bool:
    """检查 PLCSIM Advanced GUI 是否已在运行"""
    try:
        r = subprocess.run(
            ['cmd.exe', '/c', 'tasklist', '/fi',
             'IMAGENAME eq Siemens.Simatic.PlcSim.Advanced.UserInterface.exe',
             '/fo', 'csv', '/nh'],
            capture_output=True, text=True, timeout=5,
            encoding='gbk', errors='replace',
        )
        return 'Siemens.Simatic.PlcSim.Advanced.UserInterface.exe' in (r.stdout or '')
    except Exception:
        return False


def launch(timeout_sec: int = 60) -> bool:
    """启动 PLCSIM Advanced GUI（提权启动）"""
    if is_gui_running():
        print("[PLCSIM] GUI already running")
        return True

    exe_path = _find_ui_exe()
    if not exe_path:
        print("[PLCSIM] FAIL: PLCSIM Advanced not found")
        print("[PLCSIM]   Check config.yaml simulation.advanced_install_dir")
        return False

    print(f"[PLCSIM] Starting: {exe_path}")

    is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    if is_admin:
        subprocess.Popen([exe_path], shell=True)
    else:
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe_path, "", None, 1
        )
        if ret <= 32:
            print(f"[PLCSIM] FAIL: UAC elevation failed (ret={ret})")
            return False

    # 等待 GUI 启动
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if is_gui_running():
            print(f"[PLCSIM] GUI started successfully")
            time.sleep(3)  # 等 GUI 完全加载
            return True
        time.sleep(2)

    print(f"[PLCSIM] WARN: GUI not detected within {timeout_sec}s")
    print(f"[PLCSIM]   (may still be starting, continue anyway)")
    return True


def main():
    print("=" * 50)
    print("  PLCSIM Advanced GUI Launcher")
    print("=" * 50)

    if launch():
        print()
        print(f"[PLCSIM] DONE. GUI is running.")
        print(f"[PLCSIM]   Next: run plcsim_api.py restore to start instance")
        return 0
    else:
        print()
        print(f"[PLCSIM] FAILED to start GUI")
        return 1


if __name__ == "__main__":
    sys.exit(main())
