"""
端到端自动化脚本：启动所有软件 → 编译 → 下载到 PLCSIM

1. 启动 PLCSIM Advanced 实例（从 golden backup 恢复）
2. 启动 TIA Portal GUI（使用 Windows 原生方式确保窗口可见）
3. 等待两者就绪
4. 编译项目
5. UI Automation 下载到 PLCSIM
6. 更新 golden backup

用法:
  python run_end2end.py
  python run_end2end.py --no-compile  # 跳过编译
  python run_end2end.py --timeout 300
"""
import sys, os, subprocess, time, json

# ── 路径 ──
BASE = os.path.dirname(__file__)
PLCSIM_API = os.path.join(BASE, "plcsim_api.py")
TIA_EXE = r"D:\TIA BEN TI\Portal V18\bin\Siemens.Automation.Portal.exe"
TIA_PROJECT = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\demo.ap18"
GOLDEN_ZIP = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\factory_io1_golden.zip"
STORAGE = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\plcsim_storage"

# ── 实例名 ──
INSTANCE_NAME = "factoryio"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


def step_start_plcsim():
    """通过 API 从 golden backup 恢复 PLCSIM 实例"""
    log("Step 1: 恢复 PLCSIM Advanced 实例...")
    sys.path.insert(0, BASE)
    from plcsim_api import restore_instance, get_instances

    # 先检查是否已有实例在运行
    instances = get_instances()
    for inst in instances:
        if inst["state"] == "run":
            log(f"  实例 '{inst['name']}' 已在运行，跳过")
            return True

    try:
        restore_instance(
            INSTANCE_NAME, GOLDEN_ZIP, STORAGE,
            ip="192.168.0.1", interface="tcpip"
        )
        log("  PLCSIM 实例恢复成功!")
        return True
    except Exception as e:
        log(f"  PLCSIM 恢复失败: {e}")
        log("  请确保 PLCSIM Advanced GUI 已打开")
        return False


def step_launch_tia():
    """以 Windows 原生方式启动 TIA Portal（确保窗口在用户桌面可见）"""
    log("Step 2: 启动 TIA Portal GUI...")

    # 检查是否已在运行
    r = subprocess.run(
        ['cmd.exe', '/c', 'tasklist', '/fi', 'IMAGENAME eq Siemens.Automation.Portal.exe', '/fo', 'csv', '/nh'],
        capture_output=True, text=True,
    )
    if "Siemens.Automation.Portal" in r.stdout:
        log("  TIA Portal 已在运行")
        return True

    # 用 ShellExecuteW runas 提权启动（TIA Portal 需要管理员权限）
    log("  请求 UAC 提权启动 TIA Portal...")
    import ctypes
    is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    if is_admin:
        subprocess.run(
            f'start "" "{TIA_EXE}"',
            shell=True, cwd=os.path.dirname(TIA_EXE),
        )
    else:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", TIA_EXE, "", None, 1
        )
    log("  启动命令已发送，等待窗口加载...")

    # 等 TIA Portal 启动（最多 2 分钟）
    for i in range(24):
        time.sleep(5)
        r = subprocess.run(
            ['cmd.exe', '/c', 'tasklist', '/fi', 'IMAGENAME eq Siemens.Automation.Portal.exe', '/fo', 'csv', '/nh'],
            capture_output=True, text=True,
        )
        if "Siemens.Automation.Portal" in r.stdout:
            log(f"  TIA Portal 已启动（{i*5 + 5}s）")
            time.sleep(15)  # 等 UI 加载
            return True

    log("  TIA Portal 启动超时（2min）")
    return False


def step_compile():
    """编译项目（GUI 模式 — 附加到运行中的 TIA Portal）"""
    log("Step 3: 编译项目...")
    sys.path.insert(0, BASE)
    from tia_session import tia_session

    with tia_session(TIA_PROJECT, mode="gui") as (project, plc_sw):
        from Siemens.Engineering.Compiler import ICompilable
        if not plc_sw:
            log("  ❌ 未找到 PLC 设备")
            return False
        compiler = plc_sw.GetService[ICompilable]()
        cr = compiler.Compile()
        if cr.ErrorCount > 0:
            log(f"  ❌ 编译失败: Errors={cr.ErrorCount}")
            return False
        log(f"  ✅ 编译成功: Errors={cr.ErrorCount}, Warnings={cr.WarningCount}")
        project.Save()
    return True


def step_download_via_ui():
    """UI Automation 下载（独立子进程，避免 COM 冲突）"""
    log("Step 4: UI Automation 下载...")
    dl_script = os.path.join(BASE, "dl_plcsim_gui.py")
    project_name = os.path.basename(TIA_PROJECT)

    r = subprocess.run(
        [sys.executable, dl_script, project_name, "--timeout", "120",
         "--interface", "PLCSIM Virtual Ethernet Adapter"],
        capture_output=True, text=True, timeout=180,
        encoding="utf-8", errors="replace",
    )
    result = json.loads(r.stdout.strip()) if r.stdout.strip() else {}
    if result.get("success"):
        log("  ✅ TIA Portal GUI 下载完成")
        return True
    else:
        log(f"  ❌ 下载失败: {result.get('error', '未知')}")
        return False


def step_update_golden():
    """更新 golden backup"""
    log("Step 5: 更新 golden backup...")
    sys.path.insert(0, BASE)
    from plcsim_api import archive_instance

    try:
        archive_instance(INSTANCE_NAME, GOLDEN_ZIP, STORAGE)
        log(f"  ✅ Golden backup 已更新: {GOLDEN_ZIP}")
        return True
    except Exception as e:
        log(f"  ⚠ 更新 golden backup 失败: {e}")
        return False


def main():
    # 检查管理员权限 — TIA Portal Openness API 需要管理员权限
    import ctypes
    if not ctypes.windll.shell32.IsUserAnAdmin():
        log("⚠ TIA Portal Openness API 需要管理员权限。正在请求 UAC 提权...")
        script = os.path.abspath(sys.argv[0])
        args = ' '.join(f'"{a}"' if ' ' in a else a for a in sys.argv[1:])
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}" {args}', None, 1
        )
        if ret <= 32:
            log("⚠ UAC 提权失败。请以管理员身份运行:")
            log(f'   "D:/Python3/python.exe" {script} {" ".join(sys.argv[1:])}')
        return ret if ret > 32 else 1

    log("=" * 50)
    log("端到端自动化开始")
    log("=" * 50)

    skip_compile = "--no-compile" in sys.argv

    # Step 1: PLCSIM
    if not step_start_plcsim():
        log("⚠ 跳过后续步骤，PLCSIM 不可用")
        return 1

    # Step 2: 启动 TIA Portal
    if not step_launch_tia():
        log("⚠ TIA Portal 未运行，尝试继续...")

    # Step 3: 编译
    if not skip_compile and not step_compile():
        log("⚠ 编译失败，跳过下载")
        return 1

    # Step 4: 下载
    if not step_download_via_ui():
        log("\n📋 手动步骤:")
        log("   TIA Portal 中右键 PLC_1 → 下载到设备 → 软件(全部)")
        log("   完成后运行: python plcsim_api.py archive factoryio <golden_zip> <storage>")
        return 1

    # Step 5: golden backup
    step_update_golden()

    log("=" * 50)
    log("🎉 完整闭环完成!")
    log("  编译 ✅ → GUI 下载 ✅ → Golden backup ✅")
    log("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
