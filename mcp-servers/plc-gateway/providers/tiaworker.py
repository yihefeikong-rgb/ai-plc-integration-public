"""TiaWorker Provider — 项目自有开源 TIA 后端"""
from __future__ import annotations

import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from providers.base import ProviderResult, TiaProvider

# TiaWorker 命令映射：Gateway 方法名 -> TiaWorker.exe 命令
TIAWORKER_COMMAND_MAP: dict[str, str] = {
    "get_project_info": "get-project-info",
    "list_blocks": "list-blocks",
    "list_devices": "list-devices",
    "get_block_xml": "get-block-xml",
    "get_block_interface": "get-block-interface",
    "compile_project": "compile",
    "create_block": "create-block",
    "import_block_xml": "import-block",
    "delete_block": "delete-block",
}


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
        # 使用命令映射（如果存在）
        mapped = TIAWORKER_COMMAND_MAP.get(command, command)
        payload = json.dumps(data or {})
        try:
            r = subprocess.run(
                [str(self._exe), mapped, payload],
                capture_output=True, text=True, timeout=timeout,
                encoding='utf-8', errors='replace',
            )
            out = r.stdout.strip()
            if out:
                try:
                    return json.loads(out)
                except json.JSONDecodeError:
                    pass
            return {
                "success": r.returncode == 0,
                "output": out,
                "stderr": r.stderr.strip(),
                "returncode": r.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"超时 ({timeout}s)",
                    "reconcile_required": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _result(self, raw: dict, operation: str) -> ProviderResult:
        """将原始返回转换为统一的 ProviderResult"""
        ok = raw.get("success", False) or raw.get("ok", False)
        if not ok and raw.get("output") and not raw.get("error"):
            ok = True

        return ProviderResult(
            ok=ok,
            status="success" if ok else "error",
            operation=operation,
            operation_id=uuid.uuid4().hex[:16],
            provider="tiaworker",
            result=raw.get("data") or {"output": raw.get("output", "")},
            error=raw.get("error"),
            warnings=raw.get("warnings", []),
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