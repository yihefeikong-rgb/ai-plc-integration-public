"""
诊断脚本：检查 TIA Portal 下载能力

检查项:
  1. TIA Portal V18 安装版本（注册表）
  2. DownloadProvider 在 headless / GUI 模式下是否可用
  3. PLCSIM Advanced 是否在运行
  4. TIA Portal GUI 窗口的 AutomationId / ClassName（UI Automation 定位用）

用法:
  python diagnose_download.py
  python diagnose_download.py --check-gui   # 连 GUI 模式一起检查（会打开 TIA 窗口）
"""
import sys, os, subprocess, time, json

# ── 颜色（Windows GBK 兼容，不用 emoji） ──
G = "\033[92m"
Y = "\033[93m"
R = "\033[91m"
B = "\033[94m"
N = "\033[0m"

def check_label(name: str, ok: bool, detail: str = ""):
    mark = f"{G}[OK]{N}" if ok else f"{R}[FAIL]{N}"
    print(f"  {mark} {name}")
    if detail:
        for line in detail.strip().split("\n"):
            print(f"     {line}")


def step1_tia_version():
    """注册表查 TIA Portal V18 版本"""
    print(f"\n{B}═══ Step 1: TIA Portal 版本 ═══{N}")
    try:
        r = subprocess.run(
            r'reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" /s /f "TIA Portal" 2>nul',
            shell=True, capture_output=True, text=True, encoding='gbk', errors='replace',
        )
        if r.stdout:
            for line in r.stdout.split("\n"):
                if "DisplayName" in line or "DisplayVersion" in line:
                    print(f"  {line.strip()}")
            check_label("TIA Portal 已安装", True)
        else:
            # 查 Common Files 路径
            for p in [
                r"D:\TIA BEN TI\Portal V18",
                r"C:\Program Files\Siemens\Portal V18",
            ]:
                if os.path.exists(p):
                    check_label(f"TIA Portal 目录存在 ({p})", True)
                    return
            check_label("TIA Portal 未找到", False, "未在注册表和默认路径找到 V18")
    except Exception as e:
        check_label("查询注册表失败", False, str(e))


def step2_download_provider():
    """检查 DownloadProvider 在 headless 模式下是否可用"""
    print(f"\n{B}═══ Step 2: DownloadProvider 可用性检查 ═══{N}")
    headless = "--check-gui" not in sys.argv
    modes_to_check = ["headless"]
    if "--check-gui" in sys.argv:
        modes_to_check.append("gui")

    for mode in modes_to_check:
        print(f"\n  [{mode}] 模式:")
        try:
            from tia_session import tia_session

            with tia_session(mode=mode) as (project, plc_sw):
                from Siemens.Engineering.Download import DownloadProvider
                if not plc_sw:
                    check_label("PLC 软件未找到", False)
                    continue
                target_device = project.Devices[0]
                dp = target_device.GetService[DownloadProvider]()
                if dp is not None:
                    check_label("DownloadProvider 可用!", True,
                                 f"设备: {target_device.Name}")
                    # 尝试 PreConfigure
                    try:
                        config = dp.PreConfigure()
                        if config is not None:
                            check_label("PreConfigure 成功", True,
                                         "可以调用 Download()")
                        else:
                            check_label("PreConfigure 返回 null", False)
                    except Exception as e:
                        check_label(f"PreConfigure 异常", False, str(e))
                else:
                    check_label("DownloadProvider 返回 null", False,
                                 f"设备: {target_device.Name}\n这是 V18 免费版的已知限制，需要 UI Automation 绕过")
        except Exception as e:
            check_label(f"检查失败", False, str(e))


def step3_plcsim_status():
    """检测 PLCSIM Advanced 是否运行"""
    print(f"\n{B}═══ Step 3: PLCSIM Advanced 状态 ═══{N}")
    try:
        from plcsim_api import get_instances, _get_instance

        instances = get_instances()
        if instances:
            for inst in instances:
                mark = f"{G}[OK]{N}" if inst["state"] == "run" else f"{Y}[WARN]{N}"
                print(f"  {mark} [{inst['id']}] {inst['name']} — {inst['state']} ({inst['cpu_type']})")
            check_label("PLCSIM 有运行实例", True,
                         f"共 {len(instances)} 个实例")
        else:
            check_label("PLCSIM 无运行实例", False,
                         "没有已注册的 PLCSIM 实例，请先在 GUI 或 api 中启动")

        # ping 10.0.0.1
        r = subprocess.run(["ping", "10.0.0.1", "-n", "1", "-w", "1000"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            check_label("10.0.0.1 可达", True)
        else:
            check_label("10.0.0.1 ping 不通", False,
                         "PLCSIM 可能没启动或 IP 不对")
    except Exception as e:
        check_label("检查 PLCSIM 失败", False, str(e))


def step4_tia_window_info():
    """检测 TIA Portal 窗口的 UI Automation 信息（独立进程运行，避免 COM 冲突）"""
    print(f"\n{B}═══ Step 4: TIA Portal GUI 窗口信息 ═══{N}")

    # 因为 uiautomation (COM STA) 和 pythonnet/clr (MTA) 冲突，
    # 用独立进程跑 UI 检测
    probe_code = r"""
import sys, json
try:
    import uiautomation as ua
    windows = []
    for w in ua.GetRootControl().GetChildren():
        try:
            n = w.Name or ''
            cn = w.ClassName or ''
            if any(k in n.upper() for k in ['TIA', 'PORTAL', 'SIEMENS']):
                windows.append({
                    'name': n.strip(),
                    'class_name': cn,
                    'automation_id': w.AutomationId or '',
                })
        except: pass
    print(json.dumps(windows, ensure_ascii=False))
except Exception as e:
    print(json.dumps({'error': str(e)}))
"""
    try:
        r = subprocess.run(
            [sys.executable, "-c", probe_code],
            capture_output=True, text=True, timeout=30,
            encoding='utf-8', errors='replace',
        )
        if r.stdout:
            data = json.loads(r.stdout.strip())
            if isinstance(data, list):
                if data:
                    for w in data:
                        print(f"  [OK] 找到 TIA 窗口:")
                        print(f"     Name:           {w['name']}")
                        print(f"     ClassName:      {w['class_name']}")
                        print(f"     AutomationId:   {w['automation_id']}")
                else:
                    print("  [WARN] TIA Portal 窗口未打开")
                    print("     请先打开 TIA Portal GUI")
            elif isinstance(data, dict) and 'error' in data:
                print(f"  [FAIL] {data['error']}")
    except subprocess.TimeoutExpired:
        print("  [FAIL] 检测超时")
    except Exception as e:
        print(f"  [FAIL] {e}")


def step5_csharp_worker_check():
    """检查 TiaWorker.exe 中的 Download 逻辑"""
    print(f"\n{B}═══ Step 5: TiaWorker Download 逻辑 ═══{N}")
    cs_path = os.path.join(os.path.dirname(__file__), "TiaWorker", "Program.cs")
    if os.path.exists(cs_path):
        with open(cs_path, "r", encoding="utf-8") as f:
            cs = f.read()
        if "DownloadProvider" in cs:
            # 提取 Download 方法的逻辑
            if "downloadProvider == null" in cs:
                check_label("C# 端确认 DownloadProvider=null 路径", True,
                             "TiaWorker 的 Download 方法已检查过 DownloadProvider\n"
                             "当前行为: 返回 null → 提示手动下载")
            if "PreConfigure" in cs:
                check_label("C# 端有 PreConfigure 调用", True)
    else:
        check_label("TiaWorker/Program.cs 未找到", False)


def main():
    print(f"{'='*60}")
    print(f"  TIA Portal 下载能力诊断")
    print(f"  PID: {os.getpid()}")
    print(f"{'='*60}")

    step1_tia_version()
    step2_download_provider()
    step3_plcsim_status()
    step4_tia_window_info()
    step5_csharp_worker_check()

    print(f"\n{'='*60}")
    print(f"  诊断完成")
    print(f"  --check-gui: 同时检查 GUI 模式 DownloadProvider（会弹 TIA 窗口）")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()