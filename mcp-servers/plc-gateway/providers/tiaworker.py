"""TiaWorker Provider — 项目自有开源 TIA 后端"""
from __future__ import annotations

import uuid

from plc_gateway.providers.base import ProviderResult, TiaProvider
from mcp_common.tiaworker_client import TiaWorkerClient

# TiaWorker 命令映射：Gateway 方法名 -> TiaWorker.exe 命令
TIAWORKER_COMMAND_MAP: dict[str, str] = {
    "get_project_info": "get-project-info",
    "list_blocks": "list-blocks",
    "list_devices": "list-devices",
    "get_block_interface": "get-block-interface",
}


class TiaWorkerProvider(TiaProvider):
    """TiaWorker 只读 Provider — 复用共享客户端和唯一项目目标。"""

    def __init__(self, client: TiaWorkerClient, project_path: str):
        self._client = client
        self._project_path = project_path

    @property
    def name(self) -> str:
        return "tiaworker"

    @property
    def available(self) -> bool:
        return bool(self._project_path) and self._client.available

    @property
    def project_path(self) -> str:
        return self._project_path

    def _run(self, command: str, data: dict | None = None) -> dict:
        """仅通过共享客户端运行已验证的只读 TiaWorker 命令。"""
        payload = {"ProjectPath": self._project_path, **(data or {})}
        return self._client.run(command, payload, max_retries=1)

    def _result(self, raw: dict, operation: str) -> ProviderResult:
        """将原始返回转换为统一的 ProviderResult"""
        ok = raw.get("success") is True
        if not ok:
            return ProviderResult.error_result(
                operation=operation,
                provider=self.name,
                code=raw.get("error_code", "TIA_EXEC_ERROR"),
                message=raw.get("error", "TiaWorker 调用失败"),
                reconcile_required=raw.get("reconcile_required", False),
            )
        return ProviderResult(
            ok=True,
            operation=operation,
            operation_id=raw.get("operation_id") or uuid.uuid4().hex[:16],
            provider=self.name,
            result=raw.get("data") or {},
            warnings=raw.get("warnings", []),
        )

    def get_project_info(self) -> ProviderResult:
        raw = self._run(TIAWORKER_COMMAND_MAP["get_project_info"])
        return self._result(raw, "tia.project.info")

    def list_blocks(self) -> ProviderResult:
        raw = self._run(TIAWORKER_COMMAND_MAP["list_blocks"])
        return self._result(raw, "tia.block.list")

    def get_block_xml(self, block_name: str) -> ProviderResult:
        return ProviderResult.error_result(
            operation="tia.block.get_xml",
            provider=self.name,
            code="CAPABILITY_UNAVAILABLE",
            message="当前 TiaWorker 调用协议尚未验证 export-block，XML 导出不可用",
            status="unavailable",
        )

    def get_block_interface(self, block_name: str) -> ProviderResult:
        raw = self._run(TIAWORKER_COMMAND_MAP["get_block_interface"], {"BlockName": block_name})
        return self._result(raw, "tia.block.get_interface")

    def compile_project(self) -> ProviderResult:
        return ProviderResult.error_result("tia.project.compile", "Gateway 当前仅暴露只读能力", code="READ_ONLY", provider=self.name, status="blocked")

    def list_devices(self) -> ProviderResult:
        raw = self._run(TIAWORKER_COMMAND_MAP["list_devices"])
        return self._result(raw, "tia.hardware.list")

    def create_block(self, block_name: str, lang: str = "SCL") -> ProviderResult:
        return ProviderResult.error_result("tia.block.create", "Gateway 当前仅暴露只读能力", code="READ_ONLY", provider=self.name, status="blocked")

    def import_block_xml(self, xml_path: str) -> ProviderResult:
        return ProviderResult.error_result("tia.block.import", "Gateway 当前仅暴露只读能力", code="READ_ONLY", provider=self.name, status="blocked")

    def delete_block(self, block_name: str) -> ProviderResult:
        return ProviderResult.error_result("tia.block.delete", "Gateway 当前仅暴露只读能力", code="READ_ONLY", provider=self.name, status="blocked")
