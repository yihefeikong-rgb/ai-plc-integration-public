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

GOLDEN_ZIP = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\factory_io1_golden.zip"
STORAGE_PATH = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\plcsim_storage"
FIO_SCENE = r"C:\Users\huangxinyang\Documents\Factory IO\My Scenes\测试.factoryio"
FIO_EXE = r"D:\Factory IO\Factory IO.exe"

# ── 后台进程管理 ──
_procs = []


def log(msg):
    print(f"  [{time.strftime('%H:%M:%S')}] {msg}")


def check_golden():
    """检查黄金备份是否存在"""
    if not os.path.exists(GOLDEN_ZIP):
        log(f"⚠️  黄金备份不存在: {GOLDEN_ZIP}")
        log(f"   请先在 TIA Portal GUI 中下载一次，然后用 archive_instance 创建备份")
        return False
    log(f"✅  黄金备份: {GOLDEN_ZIP} ({os.path.getsize(GOLDEN_ZIP)/1024:.0f} KB)")
    return True


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
        from plcsim_api import restore_instance, get_instances
        
        # 检查是否已有实例在运行
        instances = get_instances()
        for inst in instances:
            if inst["state"] == "run":
                log(f"✅  实例 '{inst['name']}' 已在运行")
                return True
        
        # 恢复实例
        inst = restore_instance(
            name="factoryio",
            golden_zip=GOLDEN_ZIP,
            storage_path=STORAGE_PATH,
            ip="10.0.0.1",
            cpu_type="1511",
            interface="softbus",
        )
        log(f"✅  PLCSIM RUN (IP=10.0.0.1)")
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
    auto_cfg_path = r"C:\ProgramData\Real Games\Factory IO\auto.cfg"
    auto_cfg = f"""# Factory I/O 自动连接配置
# 由 start_all.py 自动生成
# 格式参见: https://docs.factoryio.com/manual/console/

ui.show_welcome_window = False
scene.load_from_path(r"{FIO_SCENE}")
drivers.siemens_s7plcsim.auto_connect = True
drivers.siemens_s7plcsim.instance_name = 'factoryio'
"""
    os.makedirs(os.path.dirname(auto_cfg_path), exist_ok=True)
    with open(auto_cfg_path, "w", encoding="utf-8") as f:
        f.write(auto_cfg)
    log(f"✅  auto.cfg 已生成: {auto_cfg_path}")
    
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
    args = parser.parse_args()

    print("=" * 50)
    print("  三端一键启动 — AI 接入 PLC")
    print("=" * 50)

    if args.mode == "stop":
        stop_all()
        return

    if args.mode in ("all", "plcsim"):
        if check_golden():
            start_plcsim()
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
    print("=" * 50)
    print("\n按 Ctrl+C 停止所有服务")


if __name__ == "__main__":
    try:
        main()
        # 保持进程存活
        while _procs:
            time.sleep(1)
            _procs = [(n, p) for n, p in _procs if p.poll() is None]
            if not _procs:
                print("\n所有服务已退出")
                break
    except KeyboardInterrupt:
        stop_all()
