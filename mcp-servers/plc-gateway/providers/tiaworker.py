"""TiaWorker Provider — 项目自有开源 TIA 后端"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .base import ProviderResult, TiaProvider


class TiaWorkerProvider(TiaProvider):
    """TiaWorker 提供者 — 调用 TiaWorker.exe 子进程"""

    def __init__(self, worker_exe: Path | str, tia_version: str = "V21"):
        self._exe = Path(worker_exe)
        self._tia_version = tia_version

    @property
    def name(self) -> str:
        return "tiaworker"

    @property
    def available(self) -> bool:
        return self._exe.exists()

    def _run(self, command: str, data: dict | None = None,
             timeout: int = 180) -> dict:
        """运行 TiaWorker.exe 子进程"""
        payload = json.dumps(data or {})
        try:
            r = subprocess.run(
                [str(self._exe), command, payload],
                capture_output=True, text=True, timeout=timeout,
                encoding='utf-8', errors='replace',
            )
            out = r.stdout.strip()
            if out:
                try:
                    return json.loads(out)
                except json.JSONDecodeError:
                    pass
            return {"success": r.returncode == 0, "output": out,
                    "stderr": r.stderr.strip(), "returncode": r.returncode}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"超时 ({timeout}s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _result(self, raw: dict, operation: str) -> ProviderResult:
        return ProviderResult(
            ok=raw.get("success", False),
            operation=operation,
            result=raw.get("data"),
            error=raw.get("error"),
            reconcile_required=raw.get("reconcile_required", False),
        )

    def get_project_info(self) -> ProviderResult:
        raw = self._run("get_project_info")
        return self._result(raw, "tia.project.info")

    def list_blocks(self) -> ProviderResult:
        raw = self._run("list_blocks")
        return self._result(raw, "tia.block.list")

    def get_block_xml(self, block_name: str) -> ProviderResult:
        raw = self._run("get_block_xml", {"block_name": block_name})
        return self._result(raw, "tia.block.get_xml")

    def get_block_interface(self, block_name: str) -> ProviderResult:
        raw = self._run("get_block_interface", {"block_name": block_name})
        return self._result(raw, "tia.block.get_interface")

    def compile_project(self) -> ProviderResult:
        raw = self._run("compile_project")
        return self._result(raw, "tia.project.compile")

    def list_devices(self) -> ProviderResult:
        raw = self._run("list_devices")
        return self._result(raw, "tia.hardware.list")

    def create_block(self, block_name: str, lang: str = "SCL") -> ProviderResult:
        raw = self._run("create_block", {"block_name": block_name, "lang": lang})
        return self._result(raw, "tia.block.create")

    def import_block_xml(self, xml_path: str) -> ProviderResult:
        raw = self._run("import_block_xml", {"xml_path": xml_path})
        return self._result(raw, "tia.block.import")

    def delete_block(self, block_name: str) -> ProviderResult:
        raw = self._run("delete_block", {"block_name": block_name})
        return self._result(raw, "tia.block.delete")