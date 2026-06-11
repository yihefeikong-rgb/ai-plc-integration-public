#!/usr/bin/env python3
"""
三端一键启动脚本: PLCSIM + Factory I/O + TIA MCP Server

用法:
    python start_all.py                    # 启动全部
    python start_all.py --plcsim-only      # 仅恢复 PLCSIM
    python start_all.py --factory-only     # 仅启动 Factory I/O
    python start_all.py --tia-only         # 仅启动 TIA MCP
    python start_all.py stop               # 停止所有
    python start_all.py --with-robot         # 启动全部 + Robot MCP
    python start_all.py --robot-only         # 仅启动 Robot MCP
"""
import sys
import os
import subprocess
import time
import json
import argparse
import asyncio
import ctypes
import os.path as op

# ── 路径配置 ──
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
TIA_MCP_DIR = os.path.join(PROJECT_ROOT, "mcp-servers", "tia-mcp")
PLCSIM_API = os.path.join(TIA_MCP_DIR, "plcsim_api.py")
SERVER_PY = os.path.join(TIA_MCP_DIR, "server.py")
ROBOT_MCP_DIR = os.path.join(PROJECT_ROOT, "mcp-servers", "robot-mcp")
ROBOT_SERVER_PY = os.path.join(ROBOT_MCP_DIR, "server.py")

# 从 config.yaml 加载配置
sys.path.insert(0, TIA_MCP_DIR)
from config_loader import cfg as _cfg

# 优先使用 V21 路径，失败则回退到 V18
V21_DIR = _cfg.simulation.golden_backup.v21_dir
V18_DIR = _cfg.simulation.golden_backup.v18_dir

GOLDEN_ZIP = _cfg.simulation.golden_backup.zip_path
STORAGE_PATH = _cfg.simulation.golden_backup.storage_path
GOLDEN_ZIP_V18 = os.path.join(V18_DIR, "factory_io1_golden.zip")
STORAGE_PATH_V18 = os.path.join(V18_DIR, "plcsim_storage")

PLC_IP = _cfg.simulation.advanced.plc_ip
FIO_SCENE = _cfg.factory_io.scene_path
FIO_EXE = _cfg.factory_io.exe_path

# ── 后台进程管理 ──
_procs = []


def log(msg):
    print(f"  [{time.strftime('%H:%M:%S')}] {msg}")


# ── PID 文件锁：防止并发执行 ──
LOCK_FILE = op.join(PROJECT_ROOT, "start_all.lock")


def _acquire_lock() -> int | None:
    """
    尝试获取 PID 锁。
    返回当前进程的 PID 表示成功获取锁，返回 None 表示已有其他实例在运行。
    """
    if op.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f:
                old_pid = int(f.read().strip())
        except (ValueError, OSError):
            old_pid = None
        if old_pid is not None:
            try:
                os.kill(old_pid, 0)  # 检查进程是否存在
                log(f"另一个 start_all.py 实例正在运行 (PID={old_pid}), 退出")
                return None
            except OSError:
                # 进程已死，清理旧锁
                pass
    try:
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
        return os.getpid()
    except OSError:
        return None


def _release_lock():
    if op.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass


def check_admin():
    """检查当前是否以管理员权限运行，非管理员时打印警告并询问是否继续。"""
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        is_admin = False
    if not is_admin:
        print("  [!] 警告：当前没有以管理员权限运行。")
        print("  [!] PLCSIM Advanced 需要管理员权限才能正常操作虚拟网卡。")
        try:
            resp = input("  是否继续? (y/N): ").strip().lower()
            if resp != "y":
                print("  已退出")
                sys.exit(0)
        except (EOFError, KeyboardInterrupt):
            print("\n  已退出")
            sys.exit(0)


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


def start_robot_mcp(scene: str = "Pick & Place (Basic)"):
    """启动 Robot MCP Server（Phase 4 工业机器人控制）"""
    if not os.path.exists(ROBOT_SERVER_PY):
        log(f"⚠️  Robot MCP 未安装: {ROBOT_SERVER_PY}")
        return False

    log(f"启动 Robot MCP Server (场景: {scene}) ...")
    proc = subprocess.Popen(
        [sys.executable, ROBOT_SERVER_PY, "--scene", scene],
        cwd=ROBOT_MCP_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _procs.append(("Robot MCP", proc))
    log(f"✅  Robot MCP Server 已启动 (PID={proc.pid})")
    time.sleep(2)
    return True


def main():
    parser = argparse.ArgumentParser(description="三端一键启动")
    parser.add_argument("mode", nargs="?", default="all",
                        choices=["all", "plcsim", "factory", "tia", "stop", "robot"],
                        help="启动模式")
    parser.add_argument('--nowait', action='store_true',
                        help='启动后不等待子进程（不保持前台）')
    parser.add_argument('--with-robot', action='store_true',
                        help='同时启动 Robot MCP Server（Phase 4）')
    parser.add_argument('--robot-only', action='store_true',
                        help='仅启动 Robot MCP Server')
    parser.add_argument('--robot-scene', default='Pick & Place (Basic)',
                        choices=['Pick & Place (Basic)', 'Palletizer'],
                        help='Robot MCP 场景 (默认: Pick & Place (Basic))')
    args = parser.parse_args()

    # ── 管理员权限检测 ──
    check_admin()

    # ── PID 文件锁（stop 模式不获取锁） ──
    if args.mode != "stop":
        pid = _acquire_lock()
        if pid is None:
            sys.exit(1)
    else:
        pid = None

    print("=" * 50)
    print("  三端一键启动 — AI 接入 PLC")
    print("=" * 50)

    if args.mode == "stop":
        stop_all()
        _release_lock()
        return

    try:
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

        if args.with_robot or args.mode == "robot":
            start_robot_mcp(args.robot_scene)

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
    finally:
        _release_lock()
