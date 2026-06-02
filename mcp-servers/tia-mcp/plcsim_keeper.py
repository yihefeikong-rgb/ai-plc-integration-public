"""
PLCSIM 实例保活脚本 — 启动 PLCSIM 实例并保持运行。

PLCSIM Advanced Runtime Manager 是 Python 进程的子进程，Python 退出后实例丢失。
这个脚本专门负责：启动 → 恢复实例 → 保持进程存活。

用法:
    python plcsim_keeper.py start          # 启动 PLCSIM（后台进程）
    python plcsim_keeper.py stop           # 停止 PLCSIM
    python plcsim_keeper.py status         # 查询状态
"""

import sys
import os
import time
import signal

PID_FILE = os.path.join(os.path.dirname(__file__), ".plcsim_keeper.pid")

# 路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TIA_MCP_DIR = os.path.join(PROJECT_ROOT, "mcp-servers", "tia-mcp")

GOLDEN_ZIP = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\factory_io1_golden.zip"
STORAGE_PATH = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\plcsim_storage"

INSTANCE_NAME = "factoryio"
INSTANCE_IP = "10.0.0.1"


def log(msg):
    print(f"[plcsim-keeper] {msg}")


def start():
    """启动 PLCSIM 实例并保持运行。"""
    sys.path.insert(0, TIA_MCP_DIR)
    
    from plcsim_api import restore_instance, get_instances, stop_instance

    # 先停止已有的
    try:
        stop_instance(INSTANCE_NAME, cleanup=True)
        time.sleep(1)
        log("已清理旧实例")
    except:
        pass

    # 恢复实例
    log(f"恢复实例 '{INSTANCE_NAME}' ...")
    inst = restore_instance(
        name=INSTANCE_NAME,
        golden_zip=GOLDEN_ZIP,
        storage_path=STORAGE_PATH,
        ip=INSTANCE_IP,
        cpu_type="1511",
        interface="softbus",
    )
    log(f"OK PLCSIM RUN (IP={INSTANCE_IP}, Name={INSTANCE_NAME})")

    # 写入 PID 文件
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    
    # 保持存活
    try:
        while True:
            time.sleep(10)
            # 每 10s 检查一次实例状态
            try:
                state = inst.OperatingState
                if str(state) == "Off":
                    log("WARN 实例已停止，尝试重新恢复...")
                    break
            except Exception as e:
                log(f"WARN 心跳检查异常: {e}")
                break
    except KeyboardInterrupt:
        log("收到退出信号，停止...")
    finally:
        stop_instance(INSTANCE_NAME, cleanup=True)
        log("实例已清理")


def stop():
    """停止 PLCSIM 实例。"""
    if os.path.exists(PID_FILE):
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        try:
            os.kill(pid, signal.SIGTERM)
            log(f"已发送终止信号给 PID {pid}")
        except:
            log(f"进程 {pid} 不存在")
        os.remove(PID_FILE)
    
    # 也尝试通过 API 停止
    try:
        sys.path.insert(0, TIA_MCP_DIR)
        from plcsim_api import stop_instance
        stop_instance(INSTANCE_NAME, cleanup=True)
        log("实例已通过 API 停止")
    except:
        pass


def status():
    """检查 PLCSIM 状态。"""
    try:
        sys.path.insert(0, TIA_MCP_DIR)
        from plcsim_api import get_instances
        instances = get_instances()
        if instances:
            for i in instances:
                print(f"  [{i['id']}] {i['name']} — {i['state']} ({i['cpu_type']})")
        else:
            print("  无运行实例")
    except Exception as e:
        print(f"  查询失败: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python plcsim_keeper.py {start|stop|status}")
        sys.exit(1)
    
    cmd = sys.argv[1]
    if cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "status":
        status()
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
