#!/usr/bin/env python3
"""
一键部署: Pick & Place 程序 → PLCSIM → Factory I/O → Robot MCP

修复版 — 使用正确的 TiaWorker 调用方式 + p3_flow 下载

用法:
  D:/Python3/python.exe mcp-servers/robot-mcp/deploy_pnp.py
  D:/Python3/python.exe mcp-servers/robot-mcp/deploy_pnp.py --skip-tia
"""

import sys, os, time, subprocess, json, tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).parent.parent.parent
TIA_MCP_DIR = PROJECT_ROOT / "mcp-servers" / "tia-mcp"
ROBOT_MCP_DIR = PROJECT_ROOT / "mcp-servers" / "robot-mcp"
SCL_FC = ROBOT_MCP_DIR / "pnp_fc.scl"
TIA_WORKER = TIA_MCP_DIR / "bin" / "TiaWorker.exe"
PNP_TAGS = ROBOT_MCP_DIR / "pnp_tags.json"

# 从统一配置加载（支持环境变量覆盖）
sys.path.insert(0, str(TIA_MCP_DIR))
from config_loader import cfg
PROJECT_PATH = getattr(cfg.tia, 'project_path', os.environ.get('TIA_PROJECT_PATH', ''))
PLC_IP = getattr(getattr(cfg.simulation, 'advanced', None), 'plc_ip', os.environ.get('PLC_IP', '192.168.0.1'))
FIO_EXE = getattr(getattr(cfg, 'factory_io', None), 'exe_path', os.environ.get('FACTORY_IO_DIR', r'D:\Factory IO\Factory IO.exe'))
GOLDEN_ZIP = getattr(getattr(cfg.simulation, 'golden_backup', None), 'zip_path', '')
if not GOLDEN_ZIP:
    GOLDEN_ZIP = os.path.join(os.path.dirname(PROJECT_PATH) if PROJECT_PATH else '', 'factory_io1_golden.zip')
STORAGE_PATH = getattr(getattr(cfg.simulation, 'golden_backup', None), 'storage_path', '')
if not STORAGE_PATH:
    STORAGE_PATH = os.path.join(os.path.dirname(PROJECT_PATH) if PROJECT_PATH else '', 'plcsim_storage')

GREEN='\033[92m'; YELLOW='\033[93m'; RED='\033[91m'; BLUE='\033[94m'; CYAN='\033[96m'; RESET='\033[0m'

def sep(t):
    print(f"\n{BLUE}{'='*60}{RESET}\n{BLUE}  {t}{RESET}\n{BLUE}{'='*60}{RESET}")
    sys.stdout.flush()

def log(msg, l="info"):
    e={"ok":"✅","warn":"⚠️","error":"❌","info":"📋","step":"▶","wait":"⏳"}.get(l,"•")
    c={"ok":GREEN,"warn":YELLOW,"error":RED,"info":BLUE,"step":CYAN}.get(l,"")
    print(f"{c}{e} {msg}{RESET}")
    sys.stdout.flush()

def run_tiaworker(command: str, payload: dict, timeout: int = 120) -> dict:
    """调用 TiaWorker.exe（和 server.py 一样的方式）"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(payload, f)
        tmp_path = f.name
    try:
        result = subprocess.run(
            [str(TIA_WORKER), command, tmp_path],
            capture_output=True, text=True, timeout=timeout,
            encoding='utf-8', errors='replace',
        )
        output = result.stdout.strip()
        if output:
            return json.loads(output)
        return {"status": "error", "error": result.stderr[:200] or "No output"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "timeout"}
    except json.JSONDecodeError:
        return {"status": "error", "error": f"Invalid JSON: {output[:200]}"}
    finally:
        try: os.unlink(tmp_path)
        except: pass

# ═════════════════════════════════════════════════════════════

def step1_plcsim():
    sep("步骤 1/7: 恢复 PLCSIM 实例")
    log("用户已确认 PLCSIM 实例 factoryio 处于 STOP（待下载）状态", "info")
    log("跳过恢复，直接使用现有实例", "ok")
    return True

def step1_create_tags():
    sep("步骤 2/7: 创建 PLC I/O 标签表")
    if not PNP_TAGS.exists():
        log(f"标签文件不存在: {PNP_TAGS}", "error")
        return False
    
    log(f"标签文件: {PNP_TAGS}", "info")
    log("调用 create_plc_tags.py ...", "step")
    
    sys.path.insert(0, str(TIA_MCP_DIR))
    from create_plc_tags import create_tags_from_json
    
    result = create_tags_from_json(str(PNP_TAGS), PROJECT_PATH)
    
    if result["status"] == "ok":
        log(f"✅ 标签创建: {result['created']} 新建, {result['skipped']} 已存在(跳过)", "ok")
        if result.get("errors"):
            for e in result["errors"]:
                log(f"  ⚠ {e}", "warn")
        return True
    else:
        log(f"标签创建失败: {result.get('error', '未知')}", "error")
        return False

def _import_one_scl(name: str, scl_path: Path) -> bool:
    """导入单个 SCL 文件到 TIA 项目"""
    scl_content = scl_path.read_text(encoding='utf-8')
    log(f"  SCL ({len(scl_content)}B): {scl_path.name}", "info")
    tmp_dir = Path(tempfile.gettempdir()) / "tia-scl"
    tmp_dir.mkdir(exist_ok=True)
    tmp_scl = tmp_dir / scl_path.name
    tmp_scl.write_text(scl_content, encoding='utf-8')
    payload = {"ProjectPath": PROJECT_PATH, "SclFilePath": str(tmp_scl)}
    result = run_tiaworker("import-scl", payload, timeout=120)
    ok = result.get("status") == "ok"
    log(f"  import {name}: {json.dumps(result, ensure_ascii=False)[:120]}", "ok" if ok else "warn")
    return ok

def step2_import_scl():
    sep("步骤 3/7: 导入 SCL 程序到 TIA 项目")
    if not TIA_WORKER.exists():
        log(f"TiaWorker 不存在: {TIA_WORKER}", "error")
        return False
    fc_ok = _import_one_scl("PnP_Control FB + DB + Main OB", SCL_FC)
    return fc_ok

def step3_compile():
    sep("步骤 4/7: 编译项目")
    log("调用 TiaWorker.exe compile ...", "step")
    result = run_tiaworker("compile", {"ProjectPath": PROJECT_PATH}, timeout=180)
    log(f"编译: {json.dumps(result, ensure_ascii=False)[:200]}", "ok" if result.get("status") == "ok" else "warn")
    return result.get("status") == "ok"

def step4_download():
    sep("步骤 5/7: 下载到 PLCSIM")
    log("调用 download_to_plcsim.py --tiaworker ...", "step")
    
    # 管理员提权：download_to_plcsim 需要管理员权限
    # 直接通过 subprocess 调用
    try:
        result = subprocess.run(
            ["D:/Python3/python.exe", str(TIA_MCP_DIR / "download_to_plcsim.py"),
             "--tiaworker", "--compile-first"],
            capture_output=True, text=True, timeout=300,
            encoding='utf-8', errors='replace',
        )
        output = (result.stdout + result.stderr)[-500:]
        log(f"下载结果: {output}", "info")
        
        # 检查是否成功
        if "✅" in output or "success" in output.lower() or result.returncode == 0:
            log("下载成功！", "ok")
            return True
        else:
            log("TiaWorker 下载未成功，尝试 p3_flow.py 兜底...", "warn")
            result2 = subprocess.run(
                ["D:/Python3/python.exe", str(PROJECT_ROOT / "p3_flow.py"),
                 "--download-only"],
                capture_output=True, text=True, timeout=300,
                encoding='utf-8', errors='replace',
            )
            log(f"p3_flow 结果: {(result2.stdout+result2.stderr)[-300:]}", "info")
            return result2.returncode == 0
    except Exception as e:
        log(f"下载异常: {e}", "error")
        return False

def step5_fio():
    sep("步骤 6/7: 启动 Factory I/O")
    if not os.path.exists(FIO_EXE):
        log(f"Factory I/O 未找到: {FIO_EXE}", "warn")
        return False
    subprocess.Popen([FIO_EXE])
    log("已启动，请手动:", "info")
    log("  File → Load Scene → Pick & Place (Basic)", "info")
    log("  F4 → Siemens S7-PLCSIM → Connect", "info")
    log("  按空格运行场景", "info")
    return True

def step6_robot():
    sep("步骤 7/7: 启动 Robot MCP Server")
    robot_server = ROBOT_MCP_DIR / "server.py"
    proc = subprocess.Popen(
        ["D:/Python3/python.exe", str(robot_server), "--ip", PLC_IP],
        cwd=str(ROBOT_MCP_DIR),
    )
    time.sleep(2)
    if proc.poll() is None:
        log(f"✅ Robot MCP Server (PID={proc.pid})", "ok")
        log("", "info")
        log("AI 命令:", "info")
        log("  get_status()   → 检查状态", "info")
        log("  go_home()      → 复位", "info")
        log("  pick_item()    → 抓取", "info")
        log("  place_item()   → 放置", "info")
        return True
    log("启动失败", "error")
    return False

# ═════════════════════════════════════════════════════════════

def main():
    import argparse
    import ctypes
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-tia", action="store_true")
    args = parser.parse_args()

    print(f"\n{CYAN}{'='*60}{RESET}")
    print(f"{CYAN}  Pick & Place 一键部署{RESET}")
    print(f"{CYAN}{'='*60}{RESET}")
    print(f"  Python:     {sys.executable}")
    print(f"  管理员:     {'✅ 是' if ctypes.windll.shell32.IsUserAnAdmin() else '❌ 否'}")
    print(f"  项目路径:   {PROJECT_PATH}")
    print(f"  标签文件:   {PNP_TAGS}")
    print(f"  SCL 文件:   {SCL_FC}")
    print(f"  PLC IP:     {PLC_IP}")
    print()
    if not ctypes.windll.shell32.IsUserAnAdmin():
        log("此脚本需要管理员权限！请以管理员身份运行", "error")
        log("右键 → 以管理员身份运行 命令提示符/PowerShell", "info")
        log(f"然后: {sys.executable} {__file__}", "info")
        return 1

    step1_plcsim()

    if not args.skip_tia:
        step1_create_tags()
        if step2_import_scl():
            step3_compile()
        else:
            log("SCL 导入失败，仍尝试下载...", "warn")
        step4_download()
    else:
        log("跳过 TIA 步骤", "warn")

    step5_fio()
    step6_robot()
    log("部署完成！", "ok")

if __name__ == "__main__":
    main()
