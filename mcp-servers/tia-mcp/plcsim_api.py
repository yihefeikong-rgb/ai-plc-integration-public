"""
PLCSIM Advanced .NET API 封装 — 入口模块，从子模块 re-export 所有函数。

用法:
    from plcsim_api import create_instance, get_instances, stop_instance

    # 创建并启动实例
    inst = create_instance("factory io1", "10.0.0.1", "255.255.255.0")

    # 从黄金备份克隆
    restore_instance("new_plc", "golden.zip", "D:\\persist\\new_plc", "10.0.0.2")

    # 查看所有已注册实例
    for info in get_instances():
        print(f"{info['name']} → {info['state']}")

    # 停止并删除
    stop_instance("factory io1")

    # 上下文管理器（自动清理）
    with PlcSimInstance("test", "10.0.0.1") as inst:
        inst.run()

依赖:
    - pythonnet (clr)
    - S7-PLCSIM Advanced V8.0（向后兼容 V5.0+）
    - DLL: C:\\Program Files (x86)\\Common Files\\Siemens\\PLCSIMADV\\API\\8.0\\...
"""
import sys

# ── 从子模块 re-export 所有公开函数 ──
from plcsim_common import (
    CPU_TYPES, ERROR_CODES, STATE_NAMES, _LICENSE_HELP,
    _decode_error, _resolve_cpu, _get_instance, _wait_for_state, _ensure_off,
)

from plcsim_instance import (
    get_instances, create_instance, stop_instance, stop_all,
    force_cleanup,
    _ensure_runtime_manager, _ensure_user_interface,
    PlcSimInstance,
)

from plcsim_backup import (
    archive_instance, restore_instance,
)

from plcsim_network import (
    switch_to_tcpip,
)


# ── CLI ──
if __name__ == "__main__":
    def _usage():
        print(__doc__)
        print("命令:")
        print("  list                         列出实例")
        print("  create <name> [ip] [cpu]     创建空壳实例")
        print("  stop <name>                  停止+删除实例")
        print("  stop-all                     停止所有")
        print("  purge <name>                 强制清理残留实例数据")
        print("  archive <name> <zip>         归档为 ZIP（黄金备份）")
        print("  restore <name> <zip> <sp>    从 ZIP 恢复")
        print("  tcpip <name> <ip>            切换到 TCP/IP")
        sys.exit(0)

    if len(sys.argv) < 2:
        _usage()

    cmd = sys.argv[1]
    try:
        if cmd == "list":
            instances = get_instances()
            if instances:
                for i in instances:
                    print(f"  [{i['id']}] {i['name']} — {i['state']} ({i['cpu_type']})")
            else:
                print("  无运行实例")

        elif cmd == "create":
            name = sys.argv[2] if len(sys.argv) > 2 else "test"
            ip = sys.argv[3] if len(sys.argv) > 3 else "192.168.0.1"
            cpu = sys.argv[4] if len(sys.argv) > 4 else "1511"
            create_instance(name, ip, cpu_type=cpu)

        elif cmd == "stop":
            stop_instance(sys.argv[2])

        elif cmd == "stop-all":
            stop_all()

        elif cmd == "purge":
            force_cleanup(sys.argv[2])

        elif cmd == "archive":
            name = sys.argv[2]
            zip_path = sys.argv[3]
            archive_instance(name, zip_path)

        elif cmd == "restore":
            name = sys.argv[2]
            zip_path = sys.argv[3]
            sp = sys.argv[4]
            ip = sys.argv[5] if len(sys.argv) > 5 else "192.168.0.1"
            restore_instance(name, zip_path, sp, ip)

        elif cmd == "tcpip":
            name = sys.argv[2]
            ip = sys.argv[3] if len(sys.argv) > 3 else "192.168.0.1"
            switch_to_tcpip(name, ip)

        else:
            print(f"未知命令: {cmd}")
            _usage()
    except Exception as e:
        msg = str(e)
        if "-30" in msg or "LicenseNotFound" in msg:
            print(f"ERR: {msg}")
            print(_LICENSE_HELP)
        else:
            decoded = _decode_error(e)
            print(f"ERR: {decoded}")
        sys.exit(1)
