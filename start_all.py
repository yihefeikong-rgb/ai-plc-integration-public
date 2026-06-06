#!/usr/bin/env python3
"""
三端一键启动脚本: PLCSIM + Factory I/O + TIA MCP Server

用法:
    python start_all.py                    # 启动全部
    python start_all.py --plcsim-only      # 仅恢复 PLCSIM
    python start_all.py --factory-only     # 仅启动 Factory I/O
    python start_all.py --tia-only         # 仅启动 TIA MCP
    python start_all.py stop               # 停止所有
"""
import sys
import os
import subprocess
import time
import json
import argparse

# ── 路径配置 ──
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
TIA_MCP_DIR = os.path.join(PROJECT_ROOT, "mcp-servers", "tia-mcp")
PLCSIM_API = os.path.join(TIA_MCP_DIR, "plcsim_api.py")
SERVER_PY = os.path.join(TIA_MCP_DIR, "server.py")

# 优先使用 V21 路径，失败则回退到 V18
V21_DIR = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo_V21"
V18_DIR = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo"

GOLDEN_ZIP = os.path.join(V21_DIR, "factory_io1_golden.zip")
STORAGE_PATH = os.path.join(V21_DIR, "plcsim_storage")
GOLDEN_ZIP_V18 = os.path.join(V18_DIR, "factory_io1_golden.zip")
STORAGE_PATH_V18 = os.path.join(V18_DIR, "plcsim_storage")

PLC_IP = "192.168.0.1"  # TCP/IP 模式，与 PLCSIM Advanced 一致
FIO_SCENE = r"C:\Users\huangxinyang\Documents\Factory IO\My Scenes\测试.factoryio"
FIO_EXE = r"D:\Factory IO\Factory IO.exe"

# ── 后台进程管理 ──
_procs = []


def log(msg):
    print(f"  [{time.strftime('%H:%M:%S')}] {msg}")


def check_golden():
    """检查黄金备份是否存在（V21/V18 双路径）"""
    global GOLDEN_ZIP, STORAGE_PATH
    if os.path.exists(GOLDEN_ZIP):
        log(f"✅  黄金备份 V21: {GOLDEN_ZIP} ({os.path.getsize(GOLDEN_ZIP)/1024:.0f} KB)")
        return True
    # 回退到 V18
    if os.path.exists(GOLDEN_ZIP_V18):
        log(f"⚠️  V21 golden 不存在，使用 V18: {GOLDEN_ZIP_V18}")
        GOLDEN_ZIP = GOLDEN_ZIP_V18
        STORAGE_PATH = STORAGE_PATH_V18
        return True
    log(f"❌  黄金备份不存在: {GOLDEN_ZIP} 或 {GOLDEN_ZIP_V18}")
    log(f"   请先在 TIA Portal GUI 中下载一次，然后用 archive_instance 创建备份")
    return False


def start_plcsim():
    """从黄金备份恢复 PLCSIM 实例"""
    log("启动 PLCSIM ...")
    
    # 检查 Runtime Manager 是否运行
    try:
        import clr
    except ImportError:
        log("❌  pythonnet 未安装，请 pip install pythonnet")
        return False

    sys.path.insert(0, TIA_MCP_DIR)
    try:
        from plcsim_api import restore_instance, get_instances, stop_instance, _ensure_user_interface
        
        # 检查是否已有实例在运行
        instances = get_instances()
        for inst in instances:
            if inst["state"] == "run":
                log(f"✅  实例 '{inst['name']}' 已在运行")
                return True
        
        # 先停止可能残留的同名实例
        for inst in instances:
            if inst["name"] == "factoryio" and inst["state"] != "off":
                log(f"  停止残留实例 factoryio ({inst['state']})...")
                stop_instance("factoryio")
        
        # 恢复实例 — TCP/IP 模式（Factory I/O S7-1200/1500 驱动通过虚拟网卡连接）
        inst = restore_instance(
            name="factoryio",
            golden_zip=GOLDEN_ZIP,
            storage_path=STORAGE_PATH,
            ip=PLC_IP,
            cpu_type="1511",
            interface="tcpip",
        )
        log(f"✅  PLCSIM RUN (实例=factoryio, TCP/IP {PLC_IP})")
        
        # 启动 PLCSIM GUI（V21 下载需要 GUI 窗口才能扫描到设备）
        log("启动 PLCSIM GUI (UserInterface)...")
        _ensure_user_interface()
        
        return True
    except Exception as e:
        log(f"❌  PLCSIM 启动失败: {e}")
        return False


def start_factory_io():
    """启动 Factory I/O 并自动连接 PLCSIM"""
    if not os.path.exists(FIO_EXE):
        log(f"⚠️  Factory I/O 未安装: {FIO_EXE}")
        log(f"   请修改脚本中的 FIO_EXE 路径")
        return False
    
    log("启动 Factory I/O ...")
    
    # 生成 auto.cfg（Factory IO 控制台命令格式）
    # 文档: https://docs.factoryio.com/manual/console/
    auto_cfg_path = r"C:\ProgramData\Real Games\Factory IO\auto.cfg"
    auto_cfg = """# Factory I/O 自动连接配置 — 由 start_all.py 生成
# 格式: https://docs.factoryio.com/manual/console/

ui.show_welcome_window = False
scene.start_in_run_mode = True
drivers.siemens_s7plcsim.auto_connect = True
drivers.siemens_s7plcsim.instance_name = 'factoryio'
drivers.siemens_s7plcsim.connection_timeout = 60
"""
    os.makedirs(os.path.dirname(auto_cfg_path), exist_ok=True)
    with open(auto_cfg_path, "w", encoding="utf-8") as f:
        f.write(auto_cfg)
    log(f"✅  auto.cfg 已生成: {auto_cfg_path}")

    # 同时写入用户 Documents（双重保障）
    user_auto_cfg = os.path.join(os.path.expanduser("~"), "Documents", "Factory IO", "auto.cfg")
    os.makedirs(os.path.dirname(user_auto_cfg), exist_ok=True)
    with open(user_auto_cfg, "w", encoding="utf-8") as f:
        f.write(auto_cfg)
    log(f"✅  auto.cfg 已生成: {user_auto_cfg}")
    
    # 启动 Factory I/O
    proc = subprocess.Popen([FIO_EXE], shell=True)
    _procs.append(("Factory I/O", proc))
    log(f"✅  Factory I/O 已启动 (PID={proc.pid})")
    return True


def start_tia_mcp():
    """启动 TIA MCP Server"""
    if not os.path.exists(SERVER_PY):
        log(f"❌  找不到 server.py: {SERVER_PY}")
        return False
    
    log("启动 TIA MCP Server ...")
    proc = subprocess.Popen(
        [sys.executable, SERVER_PY],
        cwd=TIA_MCP_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _procs.append(("TIA MCP", proc))
    log(f"✅  TIA MCP Server 已启动 (PID={proc.pid})")
    time.sleep(2)
    return True


def stop_all():
    """停止所有启动的进程"""
    log("\n停止所有服务 ...")
    for name, proc in _procs:
        try:
            proc.terminate()
            proc.wait(timeout=5)
            log(f"  ✅ {name} 已停止")
        except Exception:
            try:
                proc.kill()
                log(f"  ✅ {name} 已强制停止")
            except Exception:
                log(f"  ⚠️  {name} 停止失败")

    # 停止 PLCSIM 实例
    try:
        sys.path.insert(0, TIA_MCP_DIR)
        from plcsim_api import stop_instance
        stop_instance("factoryio", cleanup=False)
        log("  ✅ PLCSIM 实例已停止")
    except Exception:
        pass
    
    log("✅  全部停止")


def main():
    parser = argparse.ArgumentParser(description="三端一键启动")
    parser.add_argument("mode", nargs="?", default="all",
                        choices=["all", "plcsim", "factory", "tia", "stop"],
                        help="启动模式")
    parser.add_argument('--nowait', action='store_true',
                        help='启动后不等待子进程（不保持前台）')
    args = parser.parse_args()

    print("=" * 50)
    print("  三端一键启动 — AI 接入 PLC")
    print("=" * 50)

    if args.mode == "stop":
        stop_all()
        return

    # ── 启动顺序：PLCSIM → Factory I/O → TIA MCP ──
    # PLCSIM 必须先于 Factory I/O，因为 Factory I/O 通过 auto.cfg 自动连接到 PLCSIM 实例

    if args.mode in ("all", "plcsim"):
        if check_golden():
            if start_plcsim():
                log("PLCSIM 就绪，等待 3 秒让仿真稳定...")
                time.sleep(3)
            else:
                log("⚠️  PLCSIM 启动失败，后续可能无法连接")
        else:
            log("⏸  跳过 PLCSIM（无黄金备份）")

    if args.mode in ("all", "factory"):
        start_factory_io()

    if args.mode in ("all", "tia"):
        start_tia_mcp()

    print("\n" + "=" * 50)
    log("启动完成！运行状态:")
    for name, proc in _procs:
        alive = proc.poll() is None
        log(f"  {'🟢' if alive else '🔴'} {name}")
    # 检查 PLCSIM 实例
    try:
        sys.path.insert(0, TIA_MCP_DIR)
        from plcsim_api import get_instances
        for inst in get_instances():
            log(f"  {'🟢' if inst['state']=='run' else '🟡'} PLCSIM: {inst['name']} ({inst['state']})")
    except Exception:
        pass
    print("=" * 50)

    if args.nowait:
        return

    print("\n按 Ctrl+C 停止所有服务")

    # 保持进程存活
    try:
        while _procs:
            time.sleep(1)
            _procs = [(n, p) for n, p in _procs if p.poll() is None]
    except KeyboardInterrupt:
        stop_all()
