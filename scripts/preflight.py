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
from concurrent.futures import ThreadPoolExecutor
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


def _read_dotenv_value(key: str) -> str:
    """读取项目根 .env 中的单个键，避免 preflight 依赖后端包导入路径。"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return ""
    for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == key:
            return value.strip()
    return ""


# ═══════════════════════════════════════════════════════
#  检查函数
# ═══════════════════════════════════════════════════════

def check_tia_portal() -> CheckResult:
    """检查 TIA Portal 进程是否在运行。"""
    r = CheckResult("TIA Portal 运行状态")
    try:
        # 单次列出全部进程（列表参数，不经 shell），再用 Python 匹配 TIA Portal 进程名。
        # 此前 3 次 tasklist 子进程（精确过滤 + 模糊搜索）存在重复覆盖，且 shell=True 引入多余解析面。
        proc = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=10)
        lines = proc.stdout.splitlines()

        # 精确匹配主进程名（Siemens.Automation.Portal.exe / TiaPortal.exe）
        exact = [
            ln for ln in lines
            if "siemens.automation.portal.exe" in ln.lower() or "tiaportal.exe" in ln.lower()
        ]
        if exact:
            r.passed = True
            r.detail = "TIA Portal 进程已运行"
        else:
            # 模糊搜索，覆盖带版本号或其他变体
            fuzzy = [
                ln for ln in lines
                if "tiaportal" in ln.lower() or "siemens.automation.portal" in ln.lower()
            ]
            if fuzzy:
                r.passed = True
                r.detail = f"找到 TIA 相关进程: {fuzzy[0].strip()[:60]}"
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
        plcsim_dirs = [
            r"C:\Program Files\Siemens\S7-PLCSIM Advanced",
            r"D:\TIA FANG ZHEN\PLCSIMADV",
            os.getenv("PLCSIM_ADV_DIR", ""),
        ]
        install_dir = next((d for d in plcsim_dirs if d and os.path.isdir(d)), "")
        if not install_dir:
            r.detail = "未找到 PLCSIM Advanced 安装目录"
            r.suggestion = "安装 S7-PLCSIM Advanced V5.0+，或检查 config.yaml 中的 advanced_install_dir"
            return r

        root = Path(__file__).resolve().parent.parent
        api_script = root / "mcp-servers" / "tia-mcp" / "plcsim_api.py"
        proc = subprocess.run(
            [sys.executable, str(api_script), "list"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        if proc.returncode == 0:
            r.passed = True
            r.detail = f"API 查询成功；安装目录: {install_dir}"
        else:
            r.detail = "PLCSIM Advanced 已安装，但 API 查询失败"
            r.suggestion = "检查 PLCSIM Runtime Manager、许可证和当前进程权限级别"

    except Exception as e:
        r.detail = f"检查失败: {e}"
        r.suggestion = "检查 PLCSIM Advanced API 安装、运行时和权限"
    return r


def check_deepseek_api_key() -> CheckResult:
    """检查 DeepSeek API Key 是否配置。"""
    r = CheckResult("DeepSeek API Key")

    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    if deepseek_key:
        r.passed = True
        r.detail = "已从环境变量加载（值已隐藏）"
        return r

    deepseek_key = _read_dotenv_value("DEEPSEEK_API_KEY")
    if deepseek_key:
        r.passed = True
        r.detail = "已从 .env 加载（值已隐藏）"
        return r

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
    except Exception as e:
        # 不再静默吞错：yaml 损坏/权限错误等必须如实上报，避免误报“未配置 API Key”
        r.detail = f"config.yaml 检查失败: {e}"
        r.suggestion = "确认 mcp-servers/tia-mcp/config.yaml 存在且 YAML 格式正确，或改用环境变量 DEEPSEEK_API_KEY"
        return r

    r.detail = "未配置 API Key"
    r.suggestion = "设置环境变量: set DEEPSEEK_API_KEY=sk-xxx"
    return r


def check_python_dependencies() -> CheckResult:
    """检查 Python 依赖是否完整。"""
    r = CheckResult("Python 依赖")

    required = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "pydantic": "pydantic",
        "pydantic-settings": "pydantic_settings",
        "requests": "requests",
        "python-snap7": "snap7",
        "pyyaml": "yaml",
    }
    missing = []

    for pkg, import_name in required.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)

    if not missing:
        r.passed = True
        r.detail = "核心依赖已安装"
    else:
        r.detail = f"缺少 {len(missing)} 个包: {', '.join(missing)}"
        r.suggestion = f"pip install {' '.join(missing)}"

    return r


def check_factory_io() -> CheckResult:
    """检查 Factory I/O 安装路径是否可用。"""
    r = CheckResult("Factory I/O")
    candidates = [
        os.getenv("FACTORY_IO_DIR", ""),
        r"D:\Factory IO",
        r"C:\Program Files (x86)\Real Games\Factory IO",
    ]
    for base in candidates:
        if not base:
            continue
        exe = os.path.join(base, "Factory IO.exe")
        if os.path.exists(exe):
            r.passed = True
            r.detail = f"找到可执行文件: {exe}"
            return r
    r.detail = "未找到 Factory IO.exe"
    r.suggestion = "设置 FACTORY_IO_DIR，或确认 Factory I/O 已安装"
    return r


def _probe_port(port: int) -> tuple[bool, str]:
    """并行探测单个端口。

    Returns:
        (是否被占用, 错误消息)。空闲且无异常时 error 为空字符串；
        探测异常时如实返回错误消息，不静默吞掉。
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex(("127.0.0.1", port))
        return result == 0, ""
    except Exception as e:
        return False, f"端口 {port} 探测异常: {e}"
    finally:
        sock.close()


def check_ports() -> CheckResult:
    """检查 8000-8005 端口是否被占用。"""
    r = CheckResult("端口 8000-8005")
    ports = [8000, 8001, 8002, 8003, 8004, 8005]
    occupied: list[str] = []
    errors: list[str] = []

    # 各端口探测之间无状态依赖，并行探测避免最坏 ~6s 串行阻塞
    with ThreadPoolExecutor(max_workers=len(ports)) as pool:
        for port, (is_occupied, err) in zip(ports, pool.map(_probe_port, ports)):
            if err:
                errors.append(err)
            elif is_occupied:
                occupied.append(str(port))

    if errors:
        # fail-closed：端口状态无法确定时不得误报“全部空闲”
        r.detail = "; ".join(errors)
        r.suggestion = "端口探测失败，请检查本机网络/防火墙配置"
        return r

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
    checks.append(check_factory_io())
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
