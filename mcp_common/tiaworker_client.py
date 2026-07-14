"""
TiaWorker 共享客户端 — 封装 TiaWorker.exe 子进程调用。

为 plc-mcp-bridge 和 tia-mcp 提供统一的 TiaWorker 调用接口，
消除重复的子进程管理代码。

用法:
    from mcp_common.tiaworker_client import TiaWorkerClient

    client = TiaWorkerClient(exe_path="path/to/TiaWorker.exe")
    result = client.run("compile", {"projectPath": "..."})
"""

import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional


# ── 错误码定义 ──
ERR_CODES = {
    "NOT_FOUND": "TIA_ERR_001",
    "TIMEOUT": "TIA_ERR_002",
    "NO_OUTPUT": "TIA_ERR_003",
    "COMPILE_ERROR": "TIA_ERR_004",
    "EXEC_ERROR": "TIA_ERR_005",
    "JSON_DECODE": "TIA_ERR_006",
    "NOT_COMPILED": "TIA_ERR_007",
    "UNKNOWN": "TIA_ERR_999",
    "OUTCOME_UNKNOWN": "TIA_ERR_008",
}

ERR_MSGS = {
    "NOT_FOUND": "文件或资源不存在",
    "TIMEOUT": "TiaWorker 操作超时",
    "NO_OUTPUT": "TiaWorker 无输出",
    "COMPILE_ERROR": "编译失败",
    "EXEC_ERROR": "子进程执行错误",
    "JSON_DECODE": "JSON 解析失败",
    "NOT_COMPILED": "TiaWorker 程序未编译",
    "UNKNOWN": "未知错误",
    "OUTCOME_UNKNOWN": "变更操作结果未知，必须先只读对账",
}


def make_error(code_key: str, detail: str = "", **extra) -> dict:
    """构造带错误码的结构化错误响应"""
    msg = ERR_MSGS.get(code_key, ERR_MSGS["UNKNOWN"])
    err_str = f"[{ERR_CODES.get(code_key, ERR_CODES['UNKNOWN'])}] {msg}"
    if detail:
        err_str += f": {detail}"
    return {"success": False, "error": err_str, "error_code": code_key, **extra}


class TiaWorkerClient:
    """TiaWorker.exe 子进程调用客户端。

    Args:
        exe_path: TiaWorker.exe 路径
        tia_version: TIA Portal 版本号（如 "21"）
        default_timeout: 默认超时秒数
    """

    def __init__(
        self,
        exe_path: str | Path,
        tia_version: Optional[str] = None,
        default_timeout: int = 180,
    ):
        self.exe_path = Path(exe_path)
        self.tia_version = tia_version
        self.default_timeout = default_timeout

    @property
    def available(self) -> bool:
        """检查 TiaWorker.exe 是否存在"""
        return self.exe_path.exists()

    @classmethod
    def is_mutating_command(cls, command: str) -> bool:
        return command.strip().lower() in cls.MUTATING_COMMANDS

    @staticmethod
    def reconciliation_hint(command: str, operation_id: str) -> dict:
        """返回只读对账提示；绝不在客户端内重新发起原变更。"""
        readonly_command = {
            "download": "get-plc-status",
            "download-gui": "get-plc-status",
            "import-scl": "list-blocks",
            "import-scl-replace": "list-blocks",
            "create-lad": "list-blocks",
            "create-block": "list-blocks",
            "import-block": "list-blocks",
            "delete-block": "list-blocks",
            "add-tag": "list-tags",
            "delete-tag": "list-tags",
            "create-tag-table": "list-tags",
            "delete-tag-table": "list-tags",
            "create-db": "list-dbs",
            "delete-db": "list-dbs",
            "create-udt": "list-udts",
            "delete-udt": "list-udts",
        }.get(command.strip().lower(), "get-project-info")
        return {
            "operation_id": operation_id,
            "readonly_command": readonly_command,
            "instruction": "仅执行只读对账；在确认结果前不得重试原变更命令",
        }

    @classmethod
    def _outcome_unknown(cls, command: str, operation_id: str, detail: str) -> dict:
        return make_error(
            "OUTCOME_UNKNOWN",
            f"operation_id={operation_id}, {detail}",
            operation_id=operation_id,
            reconcile_required=True,
            reconciliation=cls.reconciliation_hint(command, operation_id),
        )

    def run(
        self,
        command: str,
        data: dict,
        timeout: Optional[int] = None,
        max_retries: int = 1,
        dry_run: bool = False,
        operation_id: Optional[str] = None,
    ) -> dict:
        """运行 TiaWorker.exe 命令。

        Args:
            command: TiaWorker 命令名
            data: JSON 数据参数
            timeout: 超时秒数（None 使用默认值）
            max_retries: 最大重试次数
            dry_run: 是否为预览模式

        Returns:
            {"success": True, "data": {...}, "raw": "..."} 或
            {"success": False, "error": "...", "error_code": "..."}
        """
        if not self.available:
            return make_error("NOT_COMPILED", str(self.exe_path))

        actual_timeout = timeout or self.default_timeout
        is_mutating = self.is_mutating_command(command)
        payload = dict(data)
        if is_mutating:
            operation_id = operation_id or payload.get("OperationId") or payload.get("operation_id") or uuid.uuid4().hex
            payload["OperationId"] = operation_id
            # 变更是否已经在目标系统生效无法从超时判断，因此禁止自动重试。
            retries = 0
        else:
            retries = max(0, max_retries)

        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8'
        )
        json.dump(payload, tmp)
        tmp_path = tmp.name
        tmp.close()

        try:
            last_error = None
            for attempt in range(1 + retries):
                try:
                    cmd = [str(self.exe_path)]
                    if dry_run:
                        cmd.append("--dry-run")
                    if self.tia_version:
                        cmd.append(f"--tia-major-version={self.tia_version}")
                    cmd.extend([command, tmp_path])

                    r = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=actual_timeout,
                        encoding='utf-8',
                        errors='replace',
                    )
                    out = r.stdout.strip()
                    if out:
                        try:
                            result = json.loads(out)
                            if result.get('ok') is True and r.returncode == 0:
                                response = {
                                    "success": True,
                                    "data": result.get('result', {}),
                                    "raw": out,
                                }
                                if is_mutating:
                                    response["operation_id"] = operation_id
                                return response
                            else:
                                err_msg = result.get('error', '')
                                if not err_msg and r.returncode:
                                    err_msg = f"TiaWorker 返回码 {r.returncode}"
                                return make_error("EXEC_ERROR", err_msg, operation_id=operation_id) if is_mutating else make_error("EXEC_ERROR", err_msg)
                        except json.JSONDecodeError:
                            if is_mutating:
                                return self._outcome_unknown(
                                    command, operation_id,
                                    f"无法解析 TiaWorker 输出: rc={r.returncode}, out={out[:200]}",
                                )
                            return make_error(
                                "JSON_DECODE",
                                f"rc={r.returncode}, out={out[:200]}",
                            )
                    if is_mutating:
                        return self._outcome_unknown(
                            command, operation_id, "TiaWorker 无输出",
                        )
                    return make_error("NO_OUTPUT")
                except subprocess.TimeoutExpired:
                    if is_mutating:
                        return self._outcome_unknown(
                            command, operation_id, f"超时 {actual_timeout}s",
                        )
                    last_error = make_error(
                        "TIMEOUT",
                        f"尝试 {attempt+1}/{1+retries}, 超时 {actual_timeout}s",
                    )
                    if attempt < retries:
                        continue
                    return last_error
                except Exception as e:
                    if is_mutating:
                        return self._outcome_unknown(command, operation_id, str(e))
                    return make_error("EXEC_ERROR", str(e))
            return last_error or make_error("UNKNOWN")
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    # 这些命令可能修改工程、设备或连接状态。它们绝不能在超时后自动重试。
    MUTATING_COMMANDS = frozenset({
        "import-scl", "import-scl-replace", "create-lad", "download", "download-gui",
        "create-block", "import-block", "save-project", "add-tag", "delete-tag",
        "create-tag-table", "delete-tag-table", "delete-block", "create-db", "delete-db",
        "create-udt", "delete-udt", "create-watch-table", "delete-watch-table",
        "create-project", "archive-project", "go-online", "go-offline",
    })
