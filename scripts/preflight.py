#!/usr/bin/env python3
"""
AI-PLC 前置条件检查脚本。

检查项:
    1. TIA Portal 进程是否运行
    2. PLCSIM Advanced API 是否可用
    3. DeepSeek API Key 是否配置
    4. Python 依赖是否完整
    5. 端口 8000-8005 是否被占用

用法:
    python scripts/preflight.py
    python scripts/preflight.py --json   (JSON 格式输出)
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# ── 颜色输出 ──
_RESET = "\033[0m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_BLUE = "\033[94m"
_BOLD = "\033[1m"


class CheckResult:
    """单次检查的结果"""

    def __init__(self, name: str):
        self.name = name
        self.passed: bool = False
        self.detail: str = ""
        self.suggestion: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
            "suggestion": self.suggestion,
        }


def _icon(passed: bool) -> str:
    return f"{_GREEN}PASS{_RESET}" if passed else f"{_RED}FAIL{_RESET}"


def _print_result(r: CheckResult) -> None:
    status = _icon(r.passed)
    detail = f" — {r.detail}" if r.detail else ""
    print(f"  [{status}] {r.name}{detail}")
    if not r.passed and r.suggestion:
        print(f"         {_YELLOW}建议: {r.suggestion}{_RESET}")


# ═══════════════════════════════════════════════════════
#  检查函数
# ═══════════════════════════════════════════════════════

def check_tia_portal() -> CheckResult:
    """检查 TIA Portal 进程是否在运行。"""
    r = CheckResult("TIA Portal 运行状态")
    try:
        # TIA Portal 主进程名为 Siemens.Automation.Portal.exe 或 V18/V21 变体
        cmd = 'tasklist /FI "IMAGENAME eq Siemens.Automation.Portal.exe" 2>nul'
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if "Siemens.Automation.Portal.exe" in proc.stdout:
            r.passed = True
            r.detail = "TIA Portal 进程已运行"
        else:
            # 试试带版本号
            cmd2 = 'tasklist /FI "IMAGENAME eq TiaPortal.exe" 2>nul'
            proc2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True, timeout=10)
            if "TiaPortal.exe" in proc2.stdout:
                r.passed = True
                r.detail = "TIA Portal 进程已运行 (TiaPortal.exe)"
            else:
                # 模糊搜索
                cmd3 = 'tasklist 2>nul | findstr /I "TiaPortal Siemens.Automation.Portal"'
                proc3 = subprocess.run(cmd3, shell=True, capture_output=True, text=True, timeout=10)
                if proc3.stdout.strip():
                    r.passed = True
                    r.detail = f"找到 TIA 相关进程: {proc3.stdout.strip()[:60]}"
                else:
                    r.detail = "未检测到 TIA Portal 进程"
                    r.suggestion = "打开 TIA Portal (以管理员权限运行)，确保项目已打开"
    except Exception as e:
        r.detail = f"检查失败: {e}"
        r.suggestion = "TIA Portal V18/V21 需要安装并运行"
    return r


def check_plcsim_api() -> CheckResult:
    """检查 PLCSIM Advanced API 是否可用。"""
    r = CheckResult("PLCSIM Advanced API")
    try:
        # 检查 PLCSIM Advanced 安装目录
        plcsim_dirs = [
            r"C:\Program Files\Siemens\S7-PLCSIM Advanced",
            r"D:\TIA FANG ZHEN\PLCSIMADV",
            os.getenv("PLCSIM_ADV_DIR", ""),
        ]
        found = False
        for d in plcsim_dirs:
            if d and os.path.isdir(d):
                found = True
                r.detail = f"找到安装目录: {d}"
                break

        if not found:
            r.detail = "未找到 PLCSIM Advanced 安装目录"
            r.suggestion = "安装 S7-PLCSIM Advanced V5.0+，或检查 config.yaml 中的 advanced_install_dir"

        # 尝试调 API
        try:
            cmd = 'powershell -Command "Get-WmiObject Win32_Process | Where-Object {$_.Name -like \'*PLCSIM*\'-or $_.Name -like \'*Siemens.Simatic.PlcSim*\'-or $_.Name -like \'*AdvancedSimulator*\'} | Select-Object Name,ProcessId | Format-List"'
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            if proc.stdout.strip():
                r.passed = True
                r.detail = f"{r.detail}; PLCSIM 进程已运行"
            elif found:
                r.passed = True  # 安装了但未运行也算通过
            else:
                r.suggestion = r.suggestion or "安装 S7-PLCSIM Advanced V5.0+"
        except Exception:
            if found:
                r.passed = True

    except Exception as e:
        r.detail = f"检查失败: {e}"
    return r


def check_deepseek_api_key() -> CheckResult:
    """检查 DeepSeek API Key 是否配置。"""
    r = CheckResult("DeepSeek API Key")

    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    if deepseek_key:
        masked = deepseek_key[:6] + "****" + deepseek_key[-4:] if len(deepseek_key) > 10 else "****"
        r.passed = True
        r.detail = f"已从环境变量加载: {masked}"
        return r

    # 检查 backend config
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from ai_plc_assistant.backend.config import settings
        deepseek_key = settings.deepseek_api_key
        if deepseek_key:
            masked = deepseek_key[:6] + "****" + deepseek_key[-4:] if len(deepseek_key) > 10 else "****"
            r.passed = True
            r.detail = f"已从 .env 加载: {masked}"
            return r
    except Exception:
        pass

    # 检查 config.yaml
    try:
        import yaml
        config_path = Path(__file__).resolve().parent.parent / "mcp-servers" / "tia-mcp" / "config.yaml"
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            deepseek_key = (cfg.get("deepseek", {}) or {}).get("api_key", "")
            if deepseek_key and not deepseek_key.startswith("${"):
                r.passed = True
                r.detail = "已从 config.yaml 加载"
                return r
    except Exception:
        pass

    r.detail = "未配置 API Key"
    r.suggestion = "设置环境变量: set DEEPSEEK_API_KEY=sk-xxx"
    return r


def check_python_dependencies() -> CheckResult:
    """检查 Python 依赖是否完整。"""
    r = CheckResult("Python 依赖")

    required = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "pydantic_settings",
        "requests",
        "python-snap7",
        "pyyaml",
    ]
    missing = []

    for pkg in required:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            missing.append(pkg)

    if not missing:
        r.passed = True
        r.detail = "核心依赖已安装"
    else:
        r.detail = f"缺少 {len(missing)} 个包: {', '.join(missing)}"
        r.suggestion = f"pip install {' '.join(missing)}"

    return r


def check_ports() -> CheckResult:
    """检查 8000-8005 端口是否被占用。"""
    r = CheckResult("端口 8000-8005")
    ports = [8000, 8001, 8002, 8003, 8004, 8005]
    occupied = []

    for port in ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex(("127.0.0.1", port))
            if result == 0:
                occupied.append(str(port))
        except Exception:
            pass
        finally:
            sock.close()

    if not occupied:
        r.passed = True
        r.detail = "全部空闲"
    else:
        r.detail = f"占用: {', '.join(occupied)} (共 {len(occupied)})"
        # 端口被占用不一定失败（因为可能是我们自己的服务）
        if any(p in occupied for p in ["8000", "8001"]):
            r.suggestion = f"端口 8000/8001 已被占用。停止占用进程: netstat -ano | findstr :{','.join(occupied)}"
        else:
            r.passed = True  # 非关键端口被占用不算失败

    return r


# ═══════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════

def run_preflight(json_output: bool = False) -> bool:
    """执行所有前置条件检查。

    Args:
        json_output: 以 JSON 格式输出

    Returns:
        全部检查通过返回 True
    """
    if not json_output:
        print(f"\n{_BOLD}{_BLUE}" + "=" * 56 + f"{_RESET}")
        print(f"{_BOLD}{_BLUE}   AI-PLC 前置条件检查{_RESET}")
        print(f"{_BOLD}{_BLUE}" + "=" * 56 + f"{_RESET}\n")

    t_start = time.time()

    checks: list[CheckResult] = []
    checks.append(check_tia_portal())
    checks.append(check_plcsim_api())
    checks.append(check_deepseek_api_key())
    checks.append(check_python_dependencies())
    checks.append(check_ports())

    all_pass = all(c.passed for c in checks)
    elapsed = (time.time() - t_start) * 1000

    if json_output:
        result = {
            "all_pass": all_pass,
            "duration_ms": elapsed,
            "checks": [c.as_dict() for c in checks],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for c in checks:
            _print_result(c)

        print(f"\n  {'─' * 40}")
        if all_pass:
            print(f"  {_GREEN}{_BOLD}全部检查通过{_RESET} ({elapsed:.0f}ms)")
        else:
            failed = [c.name for c in checks if not c.passed]
            print(f"  {_RED}{_BOLD}有 {len(failed)} 项检查未通过: {', '.join(failed)}{_RESET} ({elapsed:.0f}ms)")

    return all_pass


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-PLC 前置条件检查")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    success = run_preflight(json_output=args.json)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
