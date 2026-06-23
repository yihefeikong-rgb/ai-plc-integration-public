#!/usr/bin/env python3
"""
AI-PLC 端到端冒烟测试脚本。

通过 orchestrator API 调用 tia_full_pipeline 工作流，
验证从 SCL 生成到下载 PLCSIM 的完整链路。

固定 prompt: "三相异步电机正反转带急停和过载保护"

用法:
    python scripts/e2e_smoke.py
    python scripts/e2e_smoke.py --host 127.0.0.1 --port 8000
    python scripts/e2e_smoke.py --skip-snap7
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ── 颜色输出 ──
_RESET = "\033[0m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_BLUE = "\033[94m"
_CYAN = "\033[96m"
_BOLD = "\033[1m"

_FIXED_PROMPT = "三相异步电机正反转带急停和过载保护"

_logger = logging.getLogger("e2e_smoke")


# ═══════════════════════════════════════════════════════
#  辅助输出
# ═══════════════════════════════════════════════════════

def _ts() -> str:
    """当前时间字符串（精确到秒）"""
    return time.strftime("%H:%M:%S")


def _log_info(msg: str) -> None:
    print(f"[{_ts()}] {msg}")


def _log_ok(msg: str) -> None:
    print(f"[{_ts()}] {_GREEN}OK{_RESET}  {msg}")


def _log_warn(msg: str) -> None:
    print(f"[{_ts()}] {_YELLOW}WARN{_RESET} {msg}")


def _log_fail(msg: str) -> None:
    print(f"[{_ts()}] {_RED}FAIL{_RESET} {msg}")


def _log_step(step_num: int, total: int, desc: str) -> None:
    print(f"\n{_BLUE}{'=' * 56}{_RESET}")
    print(f"{_BOLD}  Step {step_num}/{total}: {desc}{_RESET}")
    print(f"{_BLUE}{'=' * 56}{_RESET}")


def _hr(title: str) -> None:
    """分隔标题"""
    print(f"\n{_CYAN}{'─' * 56}{_RESET}")
    print(f"{_CYAN}  {title}{_RESET}")
    print(f"{_CYAN}{'─' * 56}{_RESET}")


# ═══════════════════════════════════════════════════════
#  前置条件检查
# ═══════════════════════════════════════════════════════

def check_prerequisites(host: str, port: int) -> bool:
    """检查冒烟测试前置条件。

    检查项:
        1. orchestrator HTTP API 是否可达
        2. DeepSeek API Key 是否已配置

    Returns:
        所有检查通过返回 True
    """
    _hr("前置条件检查")

    all_pass = True

    # 1. orchestrator 可达性
    _log_info("检查 orchestrator API ...")
    try:
        import urllib.request

        url = f"http://{host}:{port}/health"
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=5)
        data = resp.read().decode("utf-8")
        _log_ok(f"orchestrator API 可达 ({host}:{port})")
        _log_info(f"  健康信息: {data[:200]}")
    except Exception as e:
        _log_fail(f"orchestrator API 不可达 ({host}:{port}): {e}")
        _log_info("  排查建议: 先运行 start.bat 启动所有服务")
        all_pass = False

    # 2. DeepSeek API Key
    _log_info("检查 DeepSeek API Key ...")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not deepseek_key:
        # 尝试从 backend config 读
        try:
            from ai_plc_assistant.backend.config import settings
            deepseek_key = settings.deepseek_api_key
        except Exception:
            pass

    if deepseek_key:
        masked = deepseek_key[:6] + "****" + deepseek_key[-4:] if len(deepseek_key) > 10 else "****"
        _log_ok(f"DeepSeek API Key 已配置: {masked}")
    else:
        _log_warn("DeepSeek API Key 未配置（从环境变量 DEEPSEEK_API_KEY 读取）")
        _log_info("  排查建议: 设置环境变量 DEEPSEEK_API_KEY 或在 .env 文件中配置")
        all_pass = False

    return all_pass


# ═══════════════════════════════════════════════════════
#  调用 orchestrator API
# ═══════════════════════════════════════════════════════

def call_orchestrator_workflow(
    host: str,
    port: int,
    workflow_input: dict[str, Any],
    workflow_name: str = "tia_full_pipeline",
) -> dict[str, Any]:
    """通过 HTTP API 调用编排层工作流。

    Args:
        host: orchestrator 主机
        port: orchestrator 端口
        workflow_input: 工作流输入参数
        workflow_name: 工作流名称

    Returns:
        API 响应的 JSON 字典
    """
    import json
    import urllib.request

    url = f"http://{host}:{port}/workflows/{workflow_name}/run"
    body = json.dumps({"input": workflow_input}).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": f"HTTP {e.code}: {body_text}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════
#  S7 变量读取
# ═══════════════════════════════════════════════════════

def read_plc_variables(ip: str, rack: int = 0, slot: int = 1) -> dict[str, Any]:
    """通过 snap7 读取 PLC 关键变量。

    读取变量:
        - M0.0: 电机运行位

    Returns:
        读取结果字典，含 success 和 variables
    """
    _log_step(5, 6, f"snap7 读取 PLC 变量 ({ip})")

    try:
        import snap7
        from snap7.util import get_bool

        client = snap7.client.Client()
        client.set_connection_params(ip, 0x0302, 0x22)
        t_start = time.time()

        try:
            client.connect(ip, rack, slot)
        except Exception as e:
            elapsed = (time.time() - t_start) * 1000
            _log_fail(f"snap7 连接失败: {e}")
            _log_info("  排查建议: 确认 PLCSIM Advanced 实例在运行，PLC IP 正确")
            _log_info("  可通过 'plc_list_instances' 工具确认 PLCSIM 实例")
            return {"success": False, "error": str(e), "duration_ms": elapsed}

        variables = {}
        try:
            m0_data = client.read_area(snap7.types.Areas.MK, 0, 0, 1)
            m0_0 = get_bool(m0_data, 0, 0)
            variables["M0.0"] = {"value": m0_0, "description": "电机运行位"}
        except Exception as e:
            _log_warn(f"读取 M0.0 失败: {e}")
            variables["M0.0"] = {"value": None, "error": str(e)}

        elapsed = (time.time() - t_start) * 1000

        for var_name, var_info in variables.items():
            val = var_info.get("value")
            desc = var_info.get("description", "")
            if val is not None:
                _log_ok(f"  {var_name} = {val} ({desc})")
            else:
                _log_warn(f"  {var_name}: 读取失败 ({desc})")

        client.disconnect()
        _log_ok(f"snap7 读取完成 ({elapsed:.0f}ms)")

        return {"success": True, "variables": variables, "duration_ms": elapsed}

    except ImportError:
        _log_warn("snap7 库未安装，跳过 PLC 变量读取")
        _log_info("  安装: pip install python-snap7")
        return {"success": False, "error": "snap7 未安装", "duration_ms": 0}
    except Exception as e:
        elapsed = 0
        _log_fail(f"snap7 读取异常: {e}")
        return {"success": False, "error": str(e), "duration_ms": elapsed}


# ═══════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════

def run_smoke_test(
    host: str = "127.0.0.1",
    port: int = 8000,
    project_name: str | None = None,
    project_path: str | None = None,
    plc_ip: str = "192.168.0.110",
    skip_snap7: bool = False,
) -> bool:
    """运行端到端冒烟测试。

    流程:
        1. 检查前置条件
        2. 调用 tia_full_pipeline 工作流（通过 orchestrator API）
        3. snap7 读 PLC 变量

    Returns:
        所有步骤通过返回 True
    """
    print(f"\n{_BOLD}{_BLUE}" + "=" * 56 + f"{_RESET}")
    print(f"{_BOLD}{_BLUE}   AI-PLC 端到端冒烟测试{_RESET}")
    print(f"{_BOLD}{_BLUE}" + "=" * 56 + f"{_RESET}")
    print(f"\n  Prompt: {_FIXED_PROMPT}")

    overall_start = time.time()

    # ── 默认参数 ──
    ts = time.strftime("%Y%m%d_%H%M%S")
    if project_name is None:
        project_name = f"SmokeTest_{ts}"
    if project_path is None:
        project_path = str(Path(sys.prefix).parent / "SmokeTestProjects" / project_name)

    _log_info(f"项目名: {project_name}")
    _log_info(f"项目路径: {project_path}")
    _log_info(f"PLC IP: {plc_ip}")

    # ── Step 0: 前置条件检查 ──
    _log_step(0, 6, "前置条件检查")
    if not check_prerequisites(host, port):
        _log_fail("前置条件不满足，终止冒烟测试")
        _print_troubleshooting()
        return False

    # ── Step 1: 调用 tia_full_pipeline ──
    _log_step(1, 6, f"调用 tia_full_pipeline 工作流")
    _log_info(f"目标: {_FIXED_PROMPT}")

    workflow_input = {
        "project_name": project_name,
        "project_path": project_path,
        "scl_prompt": _FIXED_PROMPT,
        "plc_ip": plc_ip,
        "rack": 0,
        "slot": 1,
    }

    t1 = time.time()
    result = call_orchestrator_workflow(host, port, workflow_input)
    t1_elapsed = (time.time() - t1) * 1000

    if result.get("ok") is True:
        _log_ok(f"tia_full_pipeline 执行成功 ({t1_elapsed:.0f}ms)")

        # 打印每步详情
        steps = result.get("steps", [])
        _log_info(f"共 {len(steps)} 个步骤:")
        for i, step in enumerate(steps):
            status = f"{_GREEN}PASS{_RESET}" if step.get("ok") else f"{_RED}FAIL{_RESET}"
            tool_name = step.get("tool", "unknown")
            duration = step.get("duration_ms", 0)
            _log_info(f"  [{i+1}] {status} {tool_name} ({duration:.0f}ms)")
            if not step.get("ok"):
                err = step.get("error", "")
                _log_warn(f"       错误: {err[:120]}")
    else:
        _log_fail(f"tia_full_pipeline 执行失败 ({t1_elapsed:.0f}ms)")
        error_msg = result.get("error", "未知错误")
        _log_fail(f"错误: {error_msg}")
        steps = result.get("steps", [])
        if steps:
            _log_info("已执行步骤:")
            for i, step in enumerate(steps):
                status = f"{_GREEN}PASS{_RESET}" if step.get("ok") else f"{_RED}FAIL{_RESET}"
                _log_info(f"  [{i+1}] {status} {step.get('tool', '?')}")
        _print_troubleshooting()
        _print_timing_report(overall_start, False)
        return False

    # ── Step 2: snap7 读变量 ──
    snap7_ok = True
    if not skip_snap7:
        snap7_result = read_plc_variables(plc_ip)
        snap7_ok = snap7_result.get("success", False)
    else:
        _log_step(5, 6, "snap7 跳过（--skip-snap7）")

    # ── 最终结果 ──
    _print_timing_report(overall_start, snap7_ok)

    return True


# ═══════════════════════════════════════════════════════
#  排查建议 & 耗时报告
# ═══════════════════════════════════════════════════════

def _print_troubleshooting() -> None:
    """输出常见问题的排查建议。"""
    _hr("排查建议")
    print(f"""
  {_YELLOW}1. 前置条件{_RESET}
     - 确认 orchestrator 已启动: start.bat
     - 确认 DeepSeek API Key 已配置: set DEEPSEEK_API_KEY=sk-xxx

  {_YELLOW}2. TIA Portal 编译失败{_RESET}
     - 确认 TIA Portal V18/V21 已安装
     - 确认以管理员权限运行 TIA Portal
     - 确认项目路径不包含中文（如默认路径含中文，修改 config.yaml）

  {_YELLOW}3. PLCSIM 下载失败{_RESET}
     - 确认 PLCSIM Advanced 已安装并启动
     - 确认 PLCSIM 实例名 "factoryio" 已创建
     - 确认 PLC IP ({_CYAN}192.168.0.110{_RESET}) 与 PLCSIM 一致

  {_YELLOW}4. snap7 连接失败{_RESET}
     - 确认 Python snap7 已安装: pip install python-snap7
     - 确认 PLCSIM 实例在运行且编程完成
     - 尝试 ping 目标 IP 确认网络可达

  {_YELLOW}5. 更多帮助{_RESET}
     - 查看文档: docs/quickstart-落地版.md
     - 查看日志: logs/orchestrator.log
""")


def _print_timing_report(overall_start: float, snap7_ok: bool) -> None:
    """输出总耗时和结果大字。"""
    total_elapsed = time.time() - overall_start
    _hr("冒烟测试完成")
    print(f"\n  总耗时: {total_elapsed:.1f}s ({total_elapsed * 1000:.0f}ms)")

    if snap7_ok:
        print(f"\n  {_GREEN}{_BOLD}  >>> 冒烟测试通过 <<<{_RESET}\n")
    else:
        print(f"\n  {_YELLOW}{_BOLD}  >>> 冒烟测试部分通过（snap7 验证失败或未执行） <<<{_RESET}\n")


# ═══════════════════════════════════════════════════════
#  入口
# ═══════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI-PLC 端到端冒烟测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""示例:
  python scripts/e2e_smoke.py
  python scripts/e2e_smoke.py --host 127.0.0.1 --port 8000
  python scripts/e2e_smoke.py --skip-snap7
  python scripts/e2e_smoke.py --project-name MyTest --project-path C:/MyTest
""",
    )
    parser.add_argument("--host", default="127.0.0.1", help="orchestrator 主机 (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="orchestrator 端口 (default: 8000)")
    parser.add_argument("--project-name", default=None, help="TIA 项目名 (default: SmokeTest_时间戳)")
    parser.add_argument("--project-path", default=None, help="TIA 项目路径 (default: 自动生成)")
    parser.add_argument("--plc-ip", default="192.168.0.110", help="PLC IP (default: 192.168.0.110)")
    parser.add_argument("--skip-snap7", action="store_true", help="跳过 snap7 变量读取")
    args = parser.parse_args()

    success = run_smoke_test(
        host=args.host,
        port=args.port,
        project_name=args.project_name,
        project_path=args.project_path,
        plc_ip=args.plc_ip,
        skip_snap7=args.skip_snap7,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    main()
