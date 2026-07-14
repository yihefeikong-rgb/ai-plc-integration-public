#!/usr/bin/env python3
"""
P3 端到端编排器 — V21 → PLCSIM → Factory I/O

纯编排器架构：不直接导入 clr / uiautomation，所有 TIA Portal/PLCSIM 操作
均通过子进程调用，避免 COM 线程模型冲突（STA vs MTA）。

流程:
  1. PLCSIM golden 恢复 → STOP（待下载状态）
  2. TiaWorker 编译 + dl_plcsim_gui.py（或 download_to_plcsim.py）下载
  3. Factory I/O 启动

用法:
    python p3_flow.py                       # 完整流程
    python p3_flow.py --download-only       # 仅编译+下载
    python p3_flow.py --skip-compile        # 不编译直接下载
    python p3_flow.py --golden-restore      # 从 golden backup 快速恢复（跳过所有）
"""
import sys, os, subprocess, time, json, tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
TIA_MCP_DIR = PROJECT_ROOT / "mcp-servers" / "tia-mcp"

# ── 配置（从 config_loader 获取，消灭硬编码） ──
sys.path.insert(0, str(TIA_MCP_DIR))
from config_loader import cfg
from config_loader import TargetConfigurationError, validate_control_target

PROJECT_PATH = ""
PLC_IP = ""
FIO_EXE = ""
PLCSIM_INSTANCE = ""
GOLDEN_ZIP = ""
STORAGE_PATH = ""

# TiaWorker 路径
TIAWORKER_EXE = str(TIA_MCP_DIR / "bin" / "TiaWorker.exe")

GREEN='\033[92m'; YELLOW='\033[93m'; RED='\033[91m'; BLUE='\033[94m'; RESET='\033[0m'


def _load_target_configuration() -> None:
    """只从唯一 target 配置加载 P3 的项目、实例和隔离 IP。"""
    global PROJECT_PATH, PLC_IP, FIO_EXE, PLCSIM_INSTANCE, GOLDEN_ZIP, STORAGE_PATH
    target = validate_control_target()
    PROJECT_PATH = str(target.project_path)
    PLC_IP = target.plc_ip
    PLCSIM_INSTANCE = target.plcsim_instance
    FIO_EXE = cfg.factory_io.exe_path
    GOLDEN_ZIP = cfg.simulation.golden_backup.zip_path
    STORAGE_PATH = cfg.simulation.golden_backup.storage_path

def log(msg, l="info"):
    e={"ok":"✅","warn":"🟡","error":"❌","info":"📋","step":"▶","wait":"⏳"}.get(l,"•")
    c={"ok":GREEN,"warn":YELLOW,"error":RED,"info":BLUE}.get(l,"")
    print(f"{c}{e} {msg}{RESET}")

def sep(t): print(f"\n{BLUE}{'='*56}{RESET}\n{BLUE}  {t}{RESET}\n{BLUE}{'='*56}{RESET}\n")


# ═══════════════════════════════════════
#  步骤 1: PLCSIM golden 恢复
# ═══════════════════════════════════════
def step1_plcsim():
    """通过 plcsim_api.py CLI 子进程恢复 golden → STOP 待下载状态"""
    sep("步骤 1: PLCSIM 仿真（STOP 待下载状态）")
    plcsim_cli = [sys.executable, str(TIA_MCP_DIR / "plcsim_api.py")]

    # 停止旧实例
    log("停止旧实例（如有）...", "step")
    subprocess.run([*plcsim_cli, "stop", PLCSIM_INSTANCE],
                   capture_output=True, timeout=30)

    # 从 golden 恢复
    log(f"从 golden 恢复: {GOLDEN_ZIP}", "step")
    r = subprocess.run(
        [*plcsim_cli, "restore", PLCSIM_INSTANCE, GOLDEN_ZIP, STORAGE_PATH, PLC_IP],
        capture_output=True, text=True, timeout=60,
        encoding='utf-8', errors='replace',
    )
    if r.returncode != 0:
        err = r.stderr.strip() or r.stdout.strip()
        log(f"PLCSIM 恢复失败: {err}", "error")
        return False

    log("PLCSIM 已恢复（黄色待下载状态）", "ok")
    # 确保 PLCSIM GUI 窗口在运行（V21 扫描设备需要）
    subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r); "
         "from plcsim_api import _ensure_user_interface; _ensure_user_interface()" % str(TIA_MCP_DIR)],
        capture_output=True, timeout=30,
    )
    time.sleep(3)
    return True


# ═══════════════════════════════════════
#  步骤 2: 编译 + 下载
# ═══════════════════════════════════════
def step2_compile():
    """通过 TiaWorker.exe 子进程编译 TIA 项目"""
    sep("步骤 2a: 编译 TIA 项目")

    if not os.path.exists(TIAWORKER_EXE):
        log(f"TiaWorker 未编译: {TIAWORKER_EXE}", "error")
        return False

    # 准备编译 JSON
    compile_input = {"ProjectPath": PROJECT_PATH}
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
    json.dump(compile_input, tmp)
    tmp_path = tmp.name
    tmp.close()

    try:
        log("启动 TiaWorker 编译...", "step")
        r = subprocess.run(
            [TIAWORKER_EXE, "compile", tmp_path],
            capture_output=True, text=True, timeout=180,
            encoding='utf-8', errors='replace',
        )
        stdout = r.stdout.strip()
        if stdout:
            try:
                result = json.loads(stdout)
                # TiaWorker 实际输出格式: { "ok": true/false, "result": { ... }, "error": null/msg }
                if result.get('ok'):
                    data = result.get('result', {})
                    if not data.get('success'):
                        log(f"编译失败: {data.get('errors', '?')} 错误", "error")
                        return False
                    log(f"编译成功: Warnings={data.get('warnings', 0)}", "ok")
                    return True
                else:
                    log(f"编译异常: {result.get('error', '?')}", "error")
                    return False
            except json.JSONDecodeError:
                log(f"编译输出解析失败: {stdout[:200]}", "error")
                return False
        else:
            log("编译无输出", "error")
            return False
    except subprocess.TimeoutExpired:
        log("编译超时（180s）", "error")
        return False
    except Exception as e:
        log(f"编译异常: {e}", "error")
        return False
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def step2_download():
    """通过 download_to_plcsim.py 子进程下载（含多级降级策略）

    使用 download_to_plcsim.py 作为子进程，它内部有 4 级降级策略：
      1. TiaWorker (C# headless) → 2. Python API (GUI) → 3. UI Automation → 4. 手动指引
    """
    sep("步骤 2b: 下载到 PLCSIM")

    dl_script = str(TIA_MCP_DIR / "download_to_plcsim.py")
    cmd = [sys.executable, dl_script]

    log("启动下载流程（TiaWorker → Python API → UI Automation → 手动指引）...", "wait")
    r = subprocess.run(
        cmd,
        capture_output=True, text=True, timeout=300,
        encoding='utf-8', errors='replace',
    )

    # 打印输出
    for line in (r.stdout or "").split("\n"):
        if line.strip():
            print(f"  {line.strip()}")

    if r.returncode == 0:
        log("下载成功！", "ok")
        return True
    else:
        log("下载失败（查看上方错误信息）", "error")
        if r.stderr:
            for line in r.stderr.strip().split("\n"):
                if line.strip():
                    log(f"stderr: {line.strip()}", "warn")
        return False


def step2_archive():
    """下载后更新 golden backup"""
    sep("步骤 2c: 更新 golden backup")
    plcsim_cli = [sys.executable, str(TIA_MCP_DIR / "plcsim_api.py")]
    r = subprocess.run(
        [*plcsim_cli, "archive", PLCSIM_INSTANCE, GOLDEN_ZIP],
        capture_output=True, text=True, timeout=60,
        encoding='utf-8', errors='replace',
    )
    if r.returncode == 0:
        log(f"Golden backup 已更新: {GOLDEN_ZIP}", "ok")
        return True
    else:
        log("Golden backup 更新失败（不影响运行）", "warn")
        return False


# ═══════════════════════════════════════
#  步骤 3: Factory I/O
# ═══════════════════════════════════════
def step3_fio():
    """写入 auto.cfg 并启动 Factory I/O"""
    sep("步骤 3: Factory I/O")
    fio_exe = str(FIO_EXE)
    if not os.path.exists(fio_exe):
        log(f"Factory I/O 未安装: {fio_exe}", "warn")
        return True  # 非致命

    cfg_text = """# Factory I/O auto config — generated by p3_flow.py
ui.show_welcome_window = False
scene.start_in_run_mode = True
drivers.siemens_s7plcsim.auto_connect = True
drivers.siemens_s7plcsim.instance_name = '""" + PLCSIM_INSTANCE + """'
drivers.siemens_s7plcsim.connection_timeout = 60
"""
    for p in [
        r'C:\ProgramData\Real Games\Factory IO\auto.cfg',
        os.path.join(os.path.expanduser('~'), 'Documents', 'Factory IO', 'auto.cfg'),
    ]:
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8-sig') as f:
                f.write(cfg_text)
            log(f"auto.cfg 已写入: {p}", "ok")
        except Exception as e:
            log(f"写入 auto.cfg 失败: {e}", "warn")

    subprocess.Popen([fio_exe])
    log("Factory I/O 已启动", "ok")
    return True


# ═══════════════════════════════════════
#  Main
# ═══════════════════════════════════════
def main():
    try:
        _load_target_configuration()
    except TargetConfigurationError as exc:
        log(f"控制目标配置无效，拒绝执行: {exc}", "error")
        return 1

    print(f"\n{'='*56}\n  P3 端到端闭环（纯编排器模式）\n{'='*56}\n")
    print(f"  项目: {os.path.basename(PROJECT_PATH)}")
    print(f"  PLCSIM: {PLCSIM_INSTANCE} @ {PLC_IP}")
    print(f"  Golden: {os.path.basename(GOLDEN_ZIP)}")
    print()

    golden_restore = '--golden-restore' in sys.argv
    only_download = '--download-only' in sys.argv
    skip_compile = '--skip-compile' in sys.argv

    # Golden Restore 快速模式：跳过所有流程，直接从备份恢复
    if golden_restore:
        print('📦 Golden Restore 模式：跳过编译/下载，直接从备份恢复 PLCSIM')
        print()
        dl_script = str(TIA_MCP_DIR / "download_to_plcsim.py")
        r = subprocess.run(
            [sys.executable, dl_script, '--golden-restore'],
            capture_output=True, text=True, timeout=120,
            encoding='utf-8', errors='replace',
        )
        for line in (r.stdout or "").split("\n"):
            if line.strip():
                print(f"  {line.strip()}")
        return 0 if r.returncode == 0 else 1

    results = {}

    # Step 1: PLCSIM
    results['plcsim'] = step1_plcsim()
    if not results['plcsim']:
        log("PLCSIM 步骤失败，终止", "error")
        sys.exit(1)

    if not only_download:
        # Step 2a: 编译
        if not skip_compile:
            results['compile'] = step2_compile()
        else:
            results['compile'] = True
            log("跳过编译", "info")

    # Step 2b: 下载
    results['download'] = step2_download()

    if results['download']:
        # Step 2c: golden backup 更新
        step2_archive()

    if not only_download:
        # Step 3: Factory I/O
        results['fio'] = step3_fio()

    # 汇总
    print(f"\n{BLUE}{'='*56}{RESET}")
    all_ok = all(results.values())
    for n, ok in results.items():
        log(f"{n}: {'✅' if ok else '❌'}")
    print(f"\n{GREEN}P3 完成{' ✅' if all_ok else ' ⚠ 部分失败'}{RESET}")
    return 0 if all_ok else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n⚠ 中断")
        sys.exit(1)
