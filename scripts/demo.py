#!/usr/bin/env python3
"""
AI-PLC 一键演示脚本。

增强版端到端冒烟测试，包含:
    - 前置条件自动检查
    - 每步进度条 + 实时计时
    - 最终输出大字提示

基于 scripts/e2e_smoke.py 实现，共享核心逻辑。

用法:
    python scripts/demo.py
    python scripts/demo.py --skip-snap7
    python scripts/demo.py --host 127.0.0.1 --port 8000
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

from mcp_common.control_target import get_control_target, require_control_ip

# ── 颜色输出 ──
_RESET = "\033[0m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_BLUE = "\033[94m"
_CYAN = "\033[96m"
_BOLD = "\033[1m"

_FIXED_PROMPT = "三相异步电机正反转带急停和过载保护"

_logger = logging.getLogger("demo")


# ═══════════════════════════════════════════════════════
#  辅助输出
# ═══════════════════════════════════════════════════════

def _ts() -> str:
    return time.strftime("%H:%M:%S")


def _log(msg: str, level: str = "info") -> None:
    icons = {"ok": f"{_GREEN}OK{_RESET}   ", "warn": f"{_YELLOW}WARN{_RESET} ", "fail": f"{_RED}FAIL{_RESET} ", "info": ""}
    print(f"[{_ts()}] {icons.get(level, '')}{msg}")


def _banner(title: str) -> None:
    width = 54
    print()
    print(f"{_CYAN}╔{'═' * width}╗{_RESET}")
    print(f"{_CYAN}║{_RESET} {_BOLD}{title:<{width}}{_RESET} {_CYAN}║{_RESET}")
    print(f"{_CYAN}╚{'═' * width}╝{_RESET}")
    print()


def _step_header(num: int, total: int, desc: str) -> None:
    print(f"\n{_BLUE}┌{'─' * 52}┐{_RESET}")
    print(f"{_BLUE}│{_RESET} {_BOLD}Step {num}/{total}:{_RESET} {desc:<{42}}{_BLUE}│{_RESET}")
    print(f"{_BLUE}└{'─' * 52}┘{_RESET}")


def _progress_bar(current: int, total: int, label: str = "", width: int = 30) -> None:
    """绘制文本进度条。"""
    pct = current / total if total > 0 else 1.0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    label_str = f" {label}" if label else ""
    print(f"\r  [{_GREEN}{bar}{_RESET}] {int(pct * 100)}%{label_str}", end="", flush=True)


def _big_result(success: bool) -> None:
    """输出大字结果。"""
    print("\n\n")
    if success:
        print(f"{_GREEN}{_BOLD}")
        print("  ╔══════════════════════════════════════╗")
        print("  ║                                      ║")
        print("  ║     >>> Demo 运行成功 <<<            ║")
        print("  ║                                      ║")
        print("  ╚══════════════════════════════════════╝")
        print(f"{_RESET}")
    else:
        print(f"{_RED}{_BOLD}")
        print("  ╔══════════════════════════════════════╗")
        print("  ║                                      ║")
        print("  ║     >>> Demo 失败 <<<               ║")
        print("  ║                                      ║")
        print("  ╚══════════════════════════════════════╝")
        print(f"{_RESET}")
    print()


# ═══════════════════════════════════════════════════════
#  核心逻辑（复用 e2e_smoke 的关键函数）
# ═══════════════════════════════════════════════════════

def _call_workflow(host: str, port: int, wf_input: dict[str, Any]) -> dict[str, Any]:
    """调用 orchestrator API 执行工作流。"""
    import json
    import urllib.request
    import urllib.error

    url = f"http://{host}:{port}/workflows/tia_full_pipeline/run"
    body = json.dumps({"input": wf_input}).encode("utf-8")

    req = urllib.request.Request(
        url, data=body,
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


def _read_snap7_variables(ip: str) -> dict[str, Any]:
    """通过 snap7 读取 PLC 变量。"""
    try:
        import snap7
        from snap7.util import get_bool

        client = snap7.client.Client()
        client.set_connection_params(ip, 0x0302, 0x22)
        t0 = time.time()

        try:
            client.connect(ip, 0, 1)
        except Exception as e:
            return {"success": False, "error": str(e), "duration_ms": (time.time() - t0) * 1000}

        variables = {}
        try:
            m0_data = client.read_area(snap7.types.Areas.MK, 0, 0, 1)
            variables["M0.0"] = {"value": get_bool(m0_data, 0, 0), "desc": "电机运行位"}
        except Exception as e:
            variables["M0.0"] = {"value": None, "error": str(e)}

        client.disconnect()
        return {"success": True, "variables": variables, "duration_ms": (time.time() - t0) * 1000}
    except ImportError:
        return {"success": False, "error": "snap7 未安装"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _check_orchestrator(host: str, port: int) -> bool:
    """快速检查 orchestrator 可达性。"""
    import urllib.request
    try:
        url = f"http://{host}:{port}/health"
        urllib.request.urlopen(urllib.request.Request(url), timeout=5)
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════
#  演示主流程
# ═══════════════════════════════════════════════════════

def run_demo(
    host: str = "127.0.0.1",
    port: int = 8000,
    project_name: str | None = None,
    project_path: str | None = None,
    plc_ip: str | None = None,
    skip_snap7: bool = False,
) -> bool:
    """运行一键演示。

    流程:
        1. 前置条件检查
        2. 调用 tia_full_pipeline（生成/编译/下载）
        3. snap7 验证
        4. 大字结果输出
    """
    target = get_control_target()
    require_control_ip(plc_ip or target.plc_ip)
    plc_ip = target.plc_ip

    # ── 启动 Banner ──
    _banner("AI-PLC 一键演示")
    _log(f"固定 Prompt: {_FIXED_PROMPT}", "info")
    _log(f"Orchestrator: http://{host}:{port}", "info")
    _log(f"PLC IP: {plc_ip}", "info")
    print()

    overall_start = time.time()

    # ── 默认参数 ──
    ts = time.strftime("%Y%m%d_%H%M%S")
    if project_name is None:
        project_name = f"Demo_{ts}"
    if project_path is None:
        project_path = str(Path(sys.prefix).parent / "DemoProjects" / project_name)

    # ═══════════════════════════════════════
    #  Step 1: 前置条件检查
    # ═══════════════════════════════════════
    _step_header(1, 4, "前置条件检查")

    _log("检查 orchestrator 连接 ...", "info")
    _progress_bar(0, 4, "orchestrator")
    if _check_orchestrator(host, port):
        _log(f"orchestrator 已就绪 ({host}:{port})", "ok")
    else:
        _log(f"orchestrator 不可达 ({host}:{port})", "fail")
        _log("请先运行 start.bat 启动所有服务", "warn")
        _big_result(False)
        return False

    _progress_bar(1, 4, "DeepSeek Key")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    if deepseek_key:
        _log("DeepSeek API Key 已配置", "ok")
    else:
        _log("DeepSeek API Key 未通过环境变量配置", "warn")
        _log("尝试从 .env / config.yaml 读取 ...", "info")
        try:
            from ai_plc_assistant.backend.config import settings
            if settings.deepseek_api_key:
                _log("DeepSeek API Key 从 .env 加载", "ok")
            else:
                _log("DeepSeek API Key 未配置（SCl 生成需要此 Key）", "warn")
        except Exception:
            _log("无法读取 backend 配置", "warn")

    _progress_bar(2, 4, "依赖检查")
    missing = []
    for pkg in ["fastapi", "uvicorn", "requests", "python-snap7", "pyyaml"]:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            missing.append(pkg)
    if missing:
        _log(f"缺少 Python 包: {', '.join(missing)}", "warn")
        _log(f"执行: pip install {' '.join(missing)}", "info")
    else:
        _log("Python 依赖完整", "ok")

    _progress_bar(4, 4, "完成")
    print()
    _log("前置检查完成", "ok")

    # ═══════════════════════════════════════
    #  Step 2: 执行 TIA 全流水线
    # ═══════════════════════════════════════
    _step_header(2, 4, f"全流水线: {_FIXED_PROMPT}")

    workflow_input = {
        "project_name": project_name,
        "project_path": project_path,
        "scl_prompt": _FIXED_PROMPT,
        "plc_ip": plc_ip,
        "rack": 0,
        "slot": 1,
    }

    _log(f"项目: {project_name}", "info")
    _log(f"路径: {project_path}", "info")
    _log("提交工作流到 orchestrator ... (此步骤约 2-5 分钟)", "info")

    t2 = time.time()
    result = _call_workflow(host, port, workflow_input)
    t2_elapsed = time.time() - t2

    if result.get("ok") is True:
        _log(f"全流水线成功 ({t2_elapsed:.1f}s)", "ok")

        steps = result.get("steps", [])
        _log(f"共 {len(steps)} 个步骤:", "info")
        for i, step in enumerate(steps):
            status = f"{_GREEN}PASS{_RESET}" if step.get("ok") else f"{_RED}FAIL{_RESET}"
            tool_name = step.get("tool", "?")
            dur = step.get("duration_ms", 0)
            print(f"    [{i+1}] {status} {tool_name} ({dur:.0f}ms)")
    else:
        _log(f"全流水线失败 ({t2_elapsed:.1f}s)", "fail")
        error_msg = result.get("error", "未知错误")
        _log(f"错误: {error_msg}", "fail")

        steps = result.get("steps", [])
        if steps:
            _log(f"已执行 {len(steps)} 步:", "info")
            for i, step in enumerate(steps):
                s = f"{_GREEN}PASS{_RESET}" if step.get("ok") else f"{_RED}FAIL{_RESET}"
                print(f"    [{i+1}] {s} {step.get('tool', '?')}")

        _log("排查要点:", "warn")
        print("    - TIA Portal 是否以管理员权限打开?")
        print("    - PLCSIM Advanced 实例是否在运行?")
        print("    - config.yaml 中的项目路径是否合法?")
        print("    - DeepSeek API Key 是否有效?")
        _big_result(False)
        return False

    # ═══════════════════════════════════════
    #  Step 3: snap7 验证
    # ═══════════════════════════════════════
    if skip_snap7:
        _step_header(3, 4, "snap7 验证 — 跳过")
        _log("已通过 --skip-snap7 跳过", "info")
    else:
        _step_header(3, 4, "snap7 PLC 变量验证")

        _log(f"连接 PLC ({plc_ip}) ...", "info")
        snap7_result = _read_snap7_variables(plc_ip)

        if snap7_result.get("success"):
            elapsed = snap7_result.get("duration_ms", 0)
            _log(f"snap7 连接成功 ({elapsed:.0f}ms)", "ok")
            for var_name, var_info in snap7_result.get("variables", {}).items():
                val = var_info.get("value")
                desc = var_info.get("desc", "")
                if val is not None:
                    _log(f"  {var_name} = {val} ({desc})", "ok")
                else:
                    _log(f"  {var_name}: 读取失败 ({desc})", "warn")
        else:
            error = snap7_result.get("error", "未知错误")
            _log(f"snap7 连接失败: {error}", "warn")
            _log("PLCSIM 可能未就绪或 PLC IP 不匹配", "info")

    # ═══════════════════════════════════════
    #  Step 4: 演示完成
    # ═══════════════════════════════════════
    _step_header(4, 4, "演示总结")

    total_elapsed = time.time() - overall_start
    print(f"\n  总耗时: {total_elapsed:.1f}s ({total_elapsed * 1000:.0f}ms)")
    print(f"  Prompt:   {_FIXED_PROMPT}")
    print(f"  项目名:   {project_name}")
    print(f"  PLC IP:   {plc_ip}")

    _big_result(True)

    # 输出下一步建议
    print(f"  {_CYAN}后续操作:{_RESET}")
    print("    - 打开 TIA Portal 查看生成的 SCL 代码")
    print("    - 运行 ops via Factory I/O 查看仿真效果")
    print(f"    - 重试: {sys.executable} scripts/demo.py")
    print()

    return True


# ═══════════════════════════════════════════════════════
#  入口
# ═══════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI-PLC 一键演示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python scripts/demo.py
  python scripts/demo.py --skip-snap7
  python scripts/demo.py --host 127.0.0.1 --port 8000
""",
    )
    parser.add_argument("--host", default="127.0.0.1", help="orchestrator 主机 (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="orchestrator 端口 (default: 8000)")
    parser.add_argument("--project-name", default=None, help="TIA 项目名")
    parser.add_argument("--project-path", default=None, help="TIA 项目路径")
    parser.add_argument("--plc-ip", default=None, help="PLC IP（仅接受 config.yaml 的唯一 target）")
    parser.add_argument("--skip-snap7", action="store_true", help="跳过 snap7 变量读取")
    args = parser.parse_args()

    success = run_demo(
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
