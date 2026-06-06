"""
项目进度自动检测脚本
一键检查：许可证状态、测试通过率、Git 活跃度、模块完成度

用法:
    python check_progress.py
"""
import sys
import os
import json
import subprocess
import time
from pathlib import Path

# 确保 UTF-8 输出
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

# 颜色定义
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'


def print_header(title: str):
    print(f"\n{BLUE}{BOLD}{'=' * 60}{RESET}")
    print(f"{BLUE}{BOLD}  {title}{RESET}")
    print(f"{BLUE}{BOLD}{'=' * 60}{RESET}\n")


def print_status(name: str, status: str, detail: str = ""):
    emoji = {"✅": GREEN, "🟡": YELLOW, "❌": RED, "🔲": ""}.get(status[:2], "")
    print(f"  {status} {name}")
    if detail:
        print(f"      {detail}")


def check_plcsim():
    """检查 PLCSIM 许可证和实例状态"""
    print_header("PLCSIM Advanced 状态")

    try:
        sys.path.insert(0, str(PROJECT_ROOT / "mcp-servers" / "tia-mcp"))
        import clr

        dll_path = r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\8.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll"
        clr.AddReference(dll_path)
        from Siemens.Simatic.Simulation.Runtime import SimulationRuntimeManager

        # 获取已注册实例
        registered = list(SimulationRuntimeManager.RegisteredInstanceInfo)

        print(f"  已注册实例: {len(registered)} 个")

        if registered:
            for info in registered:
                iface = SimulationRuntimeManager.CreateInterface(info.ID)
                state = str(iface.OperatingState).split('.')[-1]
                status = "✅" if "Run" in state else "🟡"
                print(f"    {status} {info.Name}: {state}")
        else:
            print("  🟡 无已注册实例（需从 golden.zip 恢复）")

        return True

    except Exception as e:
        msg = str(e)
        if "-30" in msg or "License" in msg:
            print(f"  ❌ 许可证问题: {msg[:100]}")
        else:
            print(f"  ❌ 检查失败: {msg[:100]}")
        return False


def check_tia_portal():
    """检查 TIA Portal 服务状态"""
    print_header("TIA Portal 状态")

    try:
        sys.path.insert(0, str(PROJECT_ROOT / "mcp-servers" / "tia-mcp"))
        import clr
        from config_loader import cfg

        tia_dir = cfg.tia.install_dir
        tia_ver = cfg.tia.version

        print(f"  版本: {tia_ver}")
        print(f"  安装路径: {tia_dir}")

        # 尝试 headless 连接
        dll_path = os.path.join(tia_dir, "PublicAPI", tia_ver, "Siemens.Engineering.dll")
        if not os.path.exists(dll_path):
            # V21 路径
            dll_path = os.path.join(tia_dir, "PublicAPI", tia_ver, "net48", "Siemens.Engineering.Base.dll")

        if os.path.exists(dll_path):
            clr.AddReference(dll_path)
            from Siemens.Engineering import TiaPortal, TiaPortalMode

            print("  API 加载: ✅")

            # 尝试连接（快速超时）
            import threading

            result = {"success": False, "error": ""}

            def try_connect():
                try:
                    tia = TiaPortal(TiaPortalMode.WithoutUserInterface)
                    result["success"] = True
                    tia.Dispose()
                except Exception as e:
                    result["error"] = str(e)

            thread = threading.Thread(target=try_connect)
            thread.daemon = True
            thread.start()
            thread.join(timeout=5)

            if result["success"]:
                print("  Headless 连接: ✅ 就绪")
            else:
                print(f"  Headless 连接: 🟡 需 GUI 初始化")
                if result["error"]:
                    print(f"      {result['error'][:100]}")

            return True
        else:
            print(f"  ❌ DLL 未找到: {dll_path}")
            return False

    except Exception as e:
        print(f"  ❌ 检查失败: {str(e)[:100]}")
        return False


def check_git_status():
    """检查 Git 提交历史"""
    print_header("Git 状态")

    try:
        os.chdir(PROJECT_ROOT)

        # 最近提交
        r = subprocess.run(
            ["git", "log", "--oneline", "-10"],
            capture_output=True, text=True, timeout=10,
            encoding='utf-8', errors='replace'
        )
        commits = r.stdout.strip().split('\n') if r.stdout else []

        print(f"  最近 10 次提交:")
        for i, line in enumerate(commits[:5], 1):
            print(f"    {i}. {line}")

        if len(commits) > 5:
            print(f"    ... 共 {len(commits)} 条")

        # 分支状态
        r = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5,
            encoding='utf-8', errors='replace'
        )
        branch = r.stdout.strip() or "unknown"
        print(f"\n  当前分支: {branch}")

        # 检查未提交更改
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
            encoding='utf-8', errors='replace'
        )
        untracked = [l for l in r.stdout.strip().split('\n') if l]
        if untracked:
            print(f"  未提交文件: {len(untracked)} 个")
        else:
            print("  未提交文件: 0 个 ✅")

        return len(commits)

    except Exception as e:
        print(f"  ❌ 检查失败: {str(e)[:100]}")
        return 0


def check_tests():
    """运行测试套件"""
    print_header("测试套件状态")

    try:
        os.chdir(PROJECT_ROOT)
        r = subprocess.run(
            ["D:/Python3/python.exe", "-m", "pytest", "tests/", "-v", "--tb=no",
             "-q", "--no-header"],
            capture_output=True, text=True, timeout=120,
            encoding='utf-8', errors='replace'
        )

        output = r.stdout + r.stderr

        # 解析结果
        if "passed" in output:
            import re
            match = re.search(r'(\d+) passed', output)
            if match:
                passed = int(match.group(1))
                match_fail = re.search(r'(\d+) failed', output)
                failed = int(match_fail.group(1)) if match_fail else 0

                status = "✅" if failed == 0 else "🟡"
                print(f"  测试结果: {status} {passed} passed, {failed} failed")

                if failed > 0:
                    # 提取失败测试名
                    failures = re.findall(r'FAILED ([\w\./]+::[\w\.]+)', output)
                    for f in failures[:3]:
                        print(f"      ❌ {f}")

                return passed, failed

        print(f"  测试运行异常")
        return 0, 0

    except Exception as e:
        print(f"  ❌ 测试失败: {str(e)[:100]}")
        return 0, 0


def check_mcp_tools():
    """检查 MCP 工具数量"""
    print_header("MCP 工具状态")

    import re

    # 扫描 tia-mcp
    tools = {}
    for root, dirs, files in os.walk(str(PROJECT_ROOT / "mcp-servers")):
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'CartGen', 'TiaWorker', 'plcsim_storage']]
        for f in files:
            if f.endswith('.py') and not f.startswith('test_'):
                path = Path(root) / f
                try:
                    with open(path, 'r', encoding='utf-8') as fp:
                        content = fp.read()
                    for t in re.findall(r'@mcp\.tool\(\)[^#]*?def\s+(\w+)', content):
                        tools[t] = str(path.relative_to(PROJECT_ROOT))
                except:
                    pass

    print(f"  MCP 工具总数: {len(tools)} 个")
    for i, (t, path) in enumerate(tools.items(), 1):
        print(f"    {i:2d}. {t:30s} ← {path}")

    return len(tools)


def check_modules():
    """检查各阶段模块状态"""
    print_header("五阶段模块状态")

    phases = [
        ("Phase 1", "OPC UA/Modbus 运行态", ["mcp-servers/opcua-mcp", "mcp-servers/modbus-mcp", "mcp-servers/mitsubishi-mcp"]),
        ("Phase 2", "AI 控制闭环 + 安全", ["safety", "run_gateway.py"]),
        ("Phase 3", "TIA Portal 工程态", ["mcp-servers/tia-mcp", "mcp-servers/tia-mcp/CartGen", "mcp-servers/tia-mcp/download_to_plcsim.py"]),
        ("Phase 4", "工业机器人", []),
        ("Phase 5", "统一编排", []),
    ]

    total = 0
    completed = 0

    for phase, desc, required in phases:
        total += 1
        missing = []

        for item in required:
            path = PROJECT_ROOT / item
            if not path.exists():
                missing.append(item)

        if not missing:
            if required:  # 有要求的才标记完成
                print(f"  {phase} {desc}: ✅ 完成")
                completed += 1
            else:
                print(f"  {phase} {desc}: 🔲 未开始")
        else:
            pct = int((len(required) - len(missing)) / len(required) * 100) if required else 0
            print(f"  {phase} {desc}: 🟡 {pct}% ({len(missing)} 缺失)")
            for m in missing:
                print(f"      ❌ {m}")

    return completed, total


def main():
    print(f"\n{BOLD}{'=' * 60}")
    print(f"  AI 接入 PLC - 项目进度自动检测")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}{RESET}\n")

    # 1. PLCSIM 检查
    plcsim_ok = check_plcsim()

    # 2. TIA Portal 检查
    tia_ok = check_tia_portal()

    # 3. Git 状态
    commits = check_git_status()

    # 4. 测试套件
    passed, failed = check_tests()

    # 5. MCP 工具
    tools_count = check_mcp_tools()

    # 6. 模块状态
    completed, total = check_modules()

    # 汇总
    print_header("项目进度汇总")

    pct = int(completed / total * 100)
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)

    print(f"  五阶段进度: [{bar}] {pct}% ({completed}/{total})")
    print(f"  PLCSIM:    {'✅ 正常' if plcsim_ok else '❌ 异常'}")
    print(f"  TIA Portal: {'✅ 就绪' if tia_ok else '🟡 需初始化'}")
    print(f"  测试通过:   {passed} passed, {failed} failed")
    print(f"  MCP 工具:   {tools_count} 个")
    print(f"  Git 提交:   {commits} 次")

    # 整体评分
    score = 0
    if plcsim_ok: score += 25
    if tia_ok: score += 25
    if failed == 0: score += 25
    if commits > 10: score += 25

    print(f"\n  整体健康度: {score}%")

    if score >= 75:
        print(f"\n  {GREEN}✅ 项目状态良好，可以继续开发！{RESET}")
    elif score >= 50:
        print(f"\n  {YELLOW}🟡 项目状态一般，注意解决遗留问题{RESET}")
    else:
        print(f"\n  {RED}❌ 项目状态需要关注{RESET}")

    print()


if __name__ == "__main__":
    main()