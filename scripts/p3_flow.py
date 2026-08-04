#!/usr/bin/env python3
"""
P3 端到端编排器 — V21 → PLCSIM → Factory I/O

纯编排器架构：不直接导入 clr / uiautomation，所有 TIA Portal/PLCSIM 操作
均通过子进程调用，避免 COM 线程模型冲突（STA vs MTA）。

流程:
  1. PLCSIM golden 恢复（plcsim_backup.restore_instance 默认 auto_run=True，
     恢复后实例为 RUN；步骤内查询并如实记录实际状态，不宣称 STOP 待下载）
  2. TiaWorker 编译 + download_to_plcsim.py 下载
  3. Factory I/O 启动

用法:
    python p3_flow.py                       # 完整流程
    python p3_flow.py --download-only       # 仅编译+下载
    python p3_flow.py --skip-compile        # 不编译直接下载
    python p3_flow.py --golden-restore      # 从 golden backup 快速恢复（跳过所有）
    python p3_flow.py --yes                 # 显式授权动态控制链（非交互环境必须）

动态控制链（恢复/编译/下载/改写 auto.cfg/启动 Factory I/O）执行前有确认门:
  交互环境输入 yes/y 确认；非交互环境未传 --yes 时 fail-closed 拒绝执行。
"""
import sys, os, subprocess, time, json, tempfile, shutil
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


def _query_instance_state(plcsim_cli, instance_name):
    """通过 plcsim_api.py list 查询实例实际状态（纯子进程，无 COM）。

    Returns:
        状态字符串（如 'run'/'stop'），查询失败或未找到返回 None。
    """
    try:
        q = subprocess.run(
            [*plcsim_cli, "list"],
            capture_output=True, text=True, timeout=30,
            encoding='utf-8', errors='replace',
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if q.returncode != 0:
        return None
    for line in (q.stdout or "").splitlines():
        if instance_name in line and "—" in line:
            return line.split("—", 1)[1].split("(", 1)[0].strip()
    return None


def _is_plcsim_gui_running() -> bool:
    """检查 PLCSIM Advanced UserInterface 进程是否在线（tasklist，无 COM）。"""
    try:
        t = subprocess.run(
            ['cmd.exe', '/c', 'tasklist', '/fi',
             'IMAGENAME eq Siemens.Simatic.PlcSim.Advanced.UserInterface.exe',
             '/fo', 'csv', '/nh'],
            capture_output=True, text=True, timeout=5,
            encoding='gbk', errors='replace',
        )
        return 'Siemens.Simatic.PlcSim.Advanced.UserInterface.exe' in (t.stdout or '')
    except Exception:
        return False


def _wait_for_gui_ready(timeout_sec=30) -> bool:
    """有界轮询 PLCSIM GUI 进程是否在线，替代无条件固定 sleep(3)。

    进程在线后再留出固定注册窗口（与 start_plcsim_gui.launch 语义一致），
    但等待有上限，不再盲等。
    """
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if _is_plcsim_gui_running():
            time.sleep(3)
            return True
        time.sleep(2)
    log(f"PLCSIM GUI 在 {timeout_sec}s 内未检测到，继续（可能仍在启动）", "warn")
    return False


# ═══════════════════════════════════════
#  步骤 1: PLCSIM golden 恢复
# ═══════════════════════════════════════
def step1_plcsim():
    """通过 plcsim_api.py CLI 子进程恢复 golden，并如实记录实例实际状态。

    plcsim_api.py CLI 的 restore 不透传 auto_run，plcsim_backup.restore_instance
    默认 auto_run=True，恢复后实例为 RUN 而非 STOP；此处以 `list` 实测状态为准，
    不再宣称“黄色待下载状态”。如需恢复后保持 STOP，须让 plcsim_api.py CLI
    支持透传 auto_run=False（跨文件改动，见 notes）。
    """
    sep("步骤 1: PLCSIM 仿真（golden 恢复）")
    plcsim_cli = [sys.executable, str(TIA_MCP_DIR / "plcsim_api.py")]

    # 停止旧实例（失败不致命：restore 内部会处理已存在实例，但必须检查并记录）
    log("停止旧实例（如有）...", "step")
    try:
        stop_r = subprocess.run(
            [*plcsim_cli, "stop", PLCSIM_INSTANCE],
            capture_output=True, text=True, timeout=30,
            encoding='utf-8', errors='replace',
        )
        if stop_r.returncode != 0:
            log(f"停止旧实例返回非零（{stop_r.returncode}）: "
                f"{(stop_r.stderr.strip() or stop_r.stdout.strip())[:200]} — 继续恢复", "warn")
    except subprocess.TimeoutExpired:
        log("停止旧实例超时（30s），继续恢复", "warn")

    # 从 golden 恢复
    log(f"从 golden 恢复: {GOLDEN_ZIP}", "step")
    try:
        r = subprocess.run(
            [*plcsim_cli, "restore", PLCSIM_INSTANCE, GOLDEN_ZIP, STORAGE_PATH, PLC_IP],
            capture_output=True, text=True, timeout=60,
            encoding='utf-8', errors='replace',
        )
    except subprocess.TimeoutExpired:
        log("PLCSIM 恢复超时（60s），终止流程", "error")
        return False
    if r.returncode != 0:
        err = r.stderr.strip() or r.stdout.strip()
        log(f"PLCSIM 恢复失败: {err}", "error")
        return False

    # 恢复后核对实际状态（restore 默认 auto_run=True，实例通常为 RUN）
    state = _query_instance_state(plcsim_cli, PLCSIM_INSTANCE)
    if state is None:
        log("PLCSIM 已恢复，但无法查询实例状态", "warn")
    elif state.lower() == "run":
        log("PLCSIM 已恢复，当前状态: RUN（restore 默认 auto_run=True；"
            "下载将针对运行中实例执行）", "warn")
    else:
        log(f"PLCSIM 已恢复，当前状态: {state}", "ok")

    # 确保 PLCSIM GUI 窗口在运行（V21 扫描设备需要）；异常/超时不得穿透崩溃
    try:
        gui_r = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, %r); "
             "from plcsim_api import _ensure_user_interface; _ensure_user_interface()" % str(TIA_MCP_DIR)],
            capture_output=True, timeout=30,
        )
        if gui_r.returncode != 0:
            log(f"PLCSIM GUI 检查子进程返回非零（{gui_r.returncode}），继续", "warn")
    except subprocess.TimeoutExpired:
        log("PLCSIM GUI 检查超时（30s），继续", "warn")
    except Exception as e:
        log(f"PLCSIM GUI 检查异常: {e}，继续", "warn")

    # 有界就绪轮询替代无条件 sleep(3)
    _wait_for_gui_ready()
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
    try:
        r = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=300,
            encoding='utf-8', errors='replace',
        )
    except subprocess.TimeoutExpired:
        log("下载超时（300s），终止流程", "error")
        return False

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
    try:
        r = subprocess.run(
            [*plcsim_cli, "archive", PLCSIM_INSTANCE, GOLDEN_ZIP],
            capture_output=True, text=True, timeout=60,
            encoding='utf-8', errors='replace',
        )
    except subprocess.TimeoutExpired:
        log("Golden backup 更新超时（60s，不影响运行）", "warn")
        return False
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
            if os.path.exists(p):
                backup = p + '.bak'
                shutil.copyfile(p, backup)
                log(f"已有 auto.cfg 已备份: {backup}", "info")
            with open(p, 'w', encoding='utf-8-sig') as f:
                f.write(cfg_text)
            log(f"auto.cfg 已写入: {p}", "ok")
        except Exception as e:
            log(f"写入 auto.cfg 失败: {e}", "warn")

    subprocess.Popen([fio_exe])
    log("Factory I/O 已启动", "ok")
    return True


def _confirm_dynamic_chain(golden_restore=False, only_download=False, skip_compile=False) -> bool:
    """动态控制链执行前的人工确认门（fail-closed）。

    完整流程会对控制目标执行: PLCSIM golden 恢复、编译、下载、改写
    Factory I/O auto.cfg（含 machine 级）、启动 Factory I/O —— 全部是写操作。
    - 交互环境（stdin 为 TTY）: 提示人工输入 yes/y 确认；
    - 非交互环境未显式传 --yes: 直接拒绝执行（fail-closed）。
    """
    if '--yes' in sys.argv:
        return True
    if golden_restore:
        steps = ["从 golden 快速恢复 PLCSIM（download_to_plcsim.py --golden-restore）"]
    else:
        steps = [
            "PLCSIM golden 恢复（restore 默认 auto_run=True → 实例 RUN）",
            "下载到 PLCSIM" if skip_compile else "编译 TIA 项目 + 下载到 PLCSIM",
        ]
        if not only_download:
            steps.append("改写 Factory I/O auto.cfg（含 machine 级）并启动 Factory I/O")
    try:
        if not sys.stdin.isatty():
            log("非交互环境未传 --yes，拒绝执行动态控制链（fail-closed）", "error")
            return False
        print(f"\n{YELLOW}⚠ 即将执行动态控制链:{RESET}")
        for i, s in enumerate(steps, 1):
            print(f"  {i}. {s}")
        ans = input("确认执行？(yes/no): ").strip().lower()
        return ans in ("yes", "y")
    except EOFError:
        log("无法获取人工确认，拒绝执行（fail-closed）", "error")
        return False


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

    # 动态控制链人工确认门（fail-closed；非交互未传 --yes 直接拒绝）
    if not _confirm_dynamic_chain(
        golden_restore=golden_restore,
        only_download=only_download,
        skip_compile=skip_compile,
    ):
        return 1

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

    # Step 2a: 编译（--download-only 同样先编译；--skip-compile 才跳过）
    if not skip_compile:
        results['compile'] = step2_compile()
        if not results['compile']:
            # 编译失败必须中止控制链（fail-closed）：不下载、不归档、
            # 不覆盖 golden baseline，避免把编译失败的项目下载进 PLCSIM。
            log("编译失败：中止下载与 golden 归档（fail-closed），恢复基线保持不变", "error")
            return 1
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
    except Exception as e:
        print(f"\n❌ 流程异常终止: {type(e).__name__}: {e}")
        sys.exit(1)
