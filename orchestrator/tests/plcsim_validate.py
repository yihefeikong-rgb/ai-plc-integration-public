#!/usr/bin/env python
"""
PLCSIM Advanced 连接验证脚本 (standalone)。

尝试以下步骤并提供清晰诊断:
  1. 检查 snap7 是否可用
  2. 尝试 S7 直连 PLCSIM (192.168.0.1, rack 0, slot 1, port 102)
  3. 如果连接成功，验证 M 区 / DB 区读写
  4. 如果连接失败，输出诊断信息和启动步骤

用法:
    python orchestrator/tests/plcsim_validate.py
"""
import sys
import subprocess
from pathlib import Path


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg: str) -> str:
    return f"{GREEN}[OK]{RESET} {msg}"


def fail(msg: str) -> str:
    return f"{RED}[FAIL]{RESET} {msg}"


def warn(msg: str) -> str:
    return f"{YELLOW}[WARN]{RESET} {msg}"


def info(msg: str) -> str:
    return f"{CYAN}[INFO]{RESET} {msg}"


def section(title: str) -> str:
    return f"\n{BOLD}{'='*60}{RESET}\n{BOLD}  {title}{RESET}\n{BOLD}{'='*60}{RESET}"


def main():
    print(f"{BOLD}PLCSIM Advanced 集成验证脚本{RESET}")
    print(f"{'='*60}")

    # ── Step 1: 检查 snap7 ──
    print(section("Step 1: 检查 python-snap7"))
    try:
        import snap7
        print(ok(f"snap7 版本: {snap7.__version__}"))
    except ImportError as e:
        print(fail(f"snap7 未安装: {e}"))
        print("  请运行: pip install python-snap7")
        return 1

    # ── Step 2: 检查 PLCSIM Advanced 进程 ──
    print(section("Step 2: 检查 PLCSIM Advanced 进程"))
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Siemens.Simatic.PlcSim.Advanced.UserInterface.exe"],
            capture_output=True, text=True, timeout=10,
        )
        if "No tasks" in result.stdout or "INFO:" in result.stdout and "0" in result.stdout:
            print(warn("PLCSIM Advanced UI 未运行"))
            print("  启动方式: D:\\TIA FANG ZHEN\\PLCSIMADV\\bin\\Siemens.Simatic.PlcSim.Advanced.UserInterface.exe")
        else:
            print(ok("PLCSIM Advanced UI 正在运行"))
    except FileNotFoundError:
        print(warn("无法执行 tasklist（非 Windows 环境？）"))

    # ── Step 3: 检查虚拟适配器 ──
    print(section("Step 3: 检查虚拟以太网适配器"))
    try:
        result = subprocess.run(
            ["ipconfig"],
            capture_output=True, text=True, timeout=10,
        )
        if "PLCSIM" in result.stdout or "Siemens" in result.stdout:
            print(ok("检测到 PLCSIM 虚拟适配器"))
        else:
            print(warn("未检测到 PLCSIM 虚拟适配器"))
            print("  可能原因: PLCSIM Advanced 未启动")
    except FileNotFoundError:
        print(warn("无法执行 ipconfig"))

    # ── Step 4: 尝试 S7 直连 ──
    print(section("Step 4: S7 直连 PLCSIM (192.168.0.1)"))
    client = None
    try:
        client = snap7.client.Client()
        print(info("尝试连接 192.168.0.1:102 (rack=0, slot=1) ..."))
        client.connect("192.168.0.1", 0, 1, 102)
        print(ok("成功连接 PLCSIM!"))

        # ── Step 5: M 区读写验证 ──
        print(section("Step 5: M 区读写验证"))

        # MB0 写入/读取
        print(info("MB0 写入 42 ..."))
        client.mb_write(0, 1, bytearray([42]))
        data = client.mb_read(0, 1)
        assert data[0] == 42, f"MB0 期望 42，实际 {data[0]}"
        print(ok(f"MB0 = {data[0]}"))

        # MW10 写入/读取
        print(info("MW10 写入 12345 ..."))
        data_w = bytearray(2)
        snap7.util.set_int(data_w, 0, 12345)
        client.mb_write(10, 2, data_w)
        data_r = client.mb_read(10, 2)
        val = snap7.util.get_int(data_r, 0)
        assert val == 12345, f"MW10 期望 12345，实际 {val}"
        print(ok(f"MW10 = {val}"))

        # MD20 写入/读取
        print(info("MD20 写入 3.14159 ..."))
        data_w = bytearray(4)
        snap7.util.set_real(data_w, 0, 3.14159)
        client.mb_write(20, 4, data_w)
        data_r = client.mb_read(20, 4)
        val = snap7.util.get_real(data_r, 0)
        assert abs(val - 3.14159) < 0.01, f"MD20 期望 3.14159，实际 {val}"
        print(ok(f"MD20 = {val:.5f}"))

        # M0.0 位写入/读取
        print(info("M0.0 写入 True ..."))
        # 先清零
        client.mb_write(0, 1, bytearray([0]))
        data = client.mb_read(0, 1)
        snap7.util.set_bool(data, 0, 0, True)
        client.mb_write(0, 1, data)
        data_r = client.mb_read(0, 1)
        bit = snap7.util.get_bool(data_r, 0, 0)
        assert bit is True, f"M0.0 期望 True，实际 {bit}"
        print(ok(f"M0.0 = {bit}"))

        # ── Step 6: DB 区读写验证 ──
        print(section("Step 6: DB 区读写验证"))
        try:
            print(info("尝试 DB1 读写 ..."))
            client.db_write(1, 0, bytearray([99]))
            data_r = client.db_read(1, 0, 1)
            assert data_r[0] == 99, f"DB1.byte0 期望 99，实际 {data_r[0]}"
            print(ok(f"DB1.byte0 = {data_r[0]}"))
        except Exception as e:
            msg = str(e).lower()
            if any(kw in msg for kw in ("not found", "doesn't exist", "error", "invalid")):
                print(warn(f"DB1 不可用（PLC 可能未加载包含 DB 的项目）: {e}"))
            else:
                print(fail(f"DB 区读写异常: {e}"))

        # ── Step 7: 断开重连 ──
        print(section("Step 7: 连接/断开生命周期"))
        client.disconnect()
        client.destroy()
        print(ok("断开连接成功"))

        client2 = snap7.client.Client()
        client2.connect("192.168.0.1", 0, 1, 102)
        print(ok("重新连接成功"))
        client2.disconnect()
        client2.destroy()
        print(ok("二次断开成功"))
        print(ok("连接/断开生命周期验证通过"))

    except Exception as e:
        print(fail(f"S7 连接失败: {type(e).__name__}: {e}"))
        if client is not None:
            try:
                client.destroy()
            except Exception:
                pass

        # ── 诊断信息 ──
        print(section("诊断信息"))
        print(info("PLCSIM Advanced 未运行或没有可用实例。"))
        print()
        print(f"{BOLD}启动 PLCSIM Advanced 的步骤:{RESET}")
        print()
        print("  方法 1: 通过 UI 启动")
        print(f"    启动程序:")
        print(f"      D:\\TIA FANG ZHEN\\PLCSIMADV\\bin\\Siemens.Simatic.PlcSim.Advanced.UserInterface.exe")
        print("    然后在 UI 中:")
        print("      1. 点击 'Create New Instance'")
        print("      2. 设置名称 (如 'factoryio')")
        print("      3. IP 地址设为 192.168.0.1")
        print("      4. 点击 'Start'")
        print()
        print("  方法 2: 通过命令行")
        print("    创建实例 (需要 PLCSIM Advanced 的 API DLL):")
        print("      Siemens.Simatic.PlcSim.Advanced.UserInterface.exe --create-instance --name factoryio --ip 192.168.0.1")
        print()
        print("  方法 3: 通过 TIA Portal")
        print("    在 TIA Portal 中直接下载项目到 PLCSIM 设备")
        print()
        print(f"{BOLD}PLCSIM Advanced V5.4 (标准版) 注意事项:{RESET}")
        print("  - 标准 PLCSIM 不支持远程 S7 连接，只能通过 TIA Portal 联机")
        print("  - 需要 PLCSIM Advanced 才能支持通过 python-snap7 的 S7 外部连接")
        print()
        print(f"{BOLD}相关工具:{RESET}")
        print("  - python-snap7 v3 纯 Python S7 库（已安装）")
        print("  - s7_adapter.py — 封装了 S7 读写的方法")
        print("  - plc_utils.py — 命令行 S7 交互工具")

    # ── 汇总 ──
    print(section("验证汇总"))
    print(f"  snap7 可用:        是")
    print(f"  已完成诊断并记录所需步骤。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
