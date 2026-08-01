#!/usr/bin/env python3
"""输出当前自然语言到 PLCSIM 主链的事实报告。"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_common.control_target import TargetConfigurationError, get_control_target
from scripts import preflight

CONFIG_PATH = ROOT / "mcp-servers" / "tia-mcp" / "config.yaml"
ENV_PATH = ROOT / ".env"


def _read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values
    for raw in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _expand(value: Any, env: dict[str, str]) -> Any:
    if not isinstance(value, str):
        return value

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        default = match.group(2) or ""
        return os.getenv(key) or env.get(key) or default

    return re.sub(r"\$\{([^}:]+)(?::([^}]*))?\}", replace, value)


def _load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _port_open(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.2)
    try:
        return sock.connect_ex(("127.0.0.1", port)) == 0
    finally:
        sock.close()


def _check_dependencies() -> dict[str, bool]:
    imports = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "requests": "requests",
        "python-snap7": "snap7",
        "pyyaml": "yaml",
    }
    result: dict[str, bool] = {}
    for pkg, import_name in imports.items():
        try:
            __import__(import_name)
            result[pkg] = True
        except ImportError:
            result[pkg] = False
    return result


def build_report() -> dict[str, Any]:
    env = _read_env()
    cfg = _load_config()

    tia = cfg.get("tia", {}) or {}
    simulation = cfg.get("simulation", {}) or {}
    factory_io = cfg.get("factory_io", {}) or {}

    target_blocker = None
    try:
        control_target = get_control_target()
    except TargetConfigurationError as exc:
        control_target = None
        target_blocker = {
            "name": "唯一控制目标",
            "detail": f"配置漂移: {exc}",
            "suggestion": "恢复 config.yaml 的已批准 V21 / factoryio / 192.168.0.1 隔离目标",
        }

    checks = [
        preflight.check_tia_portal(),
        preflight.check_plcsim_api(),
        preflight.check_deepseek_api_key(),
        preflight.check_python_dependencies(),
        preflight.check_factory_io(),
        preflight.check_ports(),
    ]

    blockers = [
        {
            "name": item.name,
            "detail": item.detail,
            "suggestion": item.suggestion,
        }
        for item in checks
        if not item.passed
    ]
    if target_blocker:
        blockers.insert(0, target_blocker)

    install_dir = _expand(tia.get("install_dir", ""), env)
    project_path = str(control_target.project_path) if control_target else ""
    tia_version = control_target.tia_version if control_target else ""
    target_plc_ip = control_target.plc_ip if control_target else ""
    instance_name = control_target.plcsim_instance if control_target else ""
    device_name = control_target.device_name if control_target else ""

    return {
        "tia": {
            "version": tia_version,
            "configured_version": tia_version,
            "project_path": project_path,
            "device_name": device_name,
            "install_dir": install_dir,
        },
        "plcsim": {
            "backend": _expand(simulation.get("backend", ""), env),
            "advanced_install_dir": _expand(simulation.get("advanced_install_dir", ""), env),
            "plc_ip": target_plc_ip,
            "config_plc_ip": target_plc_ip,
            "instance_name": instance_name,
        },
        "factory_io": {
            "exe_path": _expand(factory_io.get("exe_path", ""), env),
            "scene_path": _expand(factory_io.get("scene_path", ""), env),
        },
        "ports": {
            "orchestrator_8000": _port_open(8000),
            "backend_8005": _port_open(8005),
            "frontend_5173": _port_open(5173),
        },
        "dependencies": _check_dependencies(),
        "blockers": blockers,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="输出 AI-PLC 当前全链路事实报告")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()
    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("# Current Chain Report")
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
