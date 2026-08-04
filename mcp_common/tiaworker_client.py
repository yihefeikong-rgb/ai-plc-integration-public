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
import locale
import os
import subprocess
import tempfile
import uuid
import warnings
from pathlib import Path
from typing import Optional

from mcp_common.control_target import get_control_target, require_control_ip


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


def _decode_worker_output(raw) -> str:
    """解码 TiaWorker 子进程输出。

    TiaWorker.exe（.NET Framework 4.8，见 TiaWorker.csproj）未设置
    Console.OutputEncoding，在中文 Windows 上按系统 ACP（GBK）输出。
    先按严格 UTF-8 解码，失败时回退系统默认编码/GBK，避免 errors='replace'
    把中文块名或错误信息替换为 U+FFFD 乱码。
    """
    if isinstance(raw, str):
        return raw
    if not raw:
        return ""
    candidates = ("utf-8-sig", "utf-8", "gbk", locale.getpreferredencoding(False), "cp1252")
    for enc in candidates:
        try:
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace")


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

    @classmethod
    def is_readonly_command(cls, command: str) -> bool:
        return command.strip().lower() in cls.READONLY_COMMANDS

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
            max_retries: 只读命令在超时/无输出/解析失败/执行错误时的最大重试
                         次数；变更命令一律不自动重试（结果未知时只能只读对账）。
            dry_run: 是否为预览模式
            operation_id: 变更操作的稳定操作 ID（未提供时自动生成）

        Returns:
            {"success": True, "data": {...}, "raw": "..."} 或
            {"success": False, "error": "...", "error_code": "..."}
        """
        if not self.available:
            return make_error("NOT_COMPILED", str(self.exe_path))

        actual_timeout = timeout or self.default_timeout
        # fail-closed：只有明确只读白名单内的命令才允许有限重试；
        # 未列明/新增的命令一律按变更处理（注入 OperationId、禁止自动重试），
        # 防止实际变更在结果未知时被自动重试。
        is_mutating = not self.is_readonly_command(command)
        payload = dict(data)
        if is_mutating:
            operation_id = operation_id or payload.get("OperationId") or payload.get("operation_id") or uuid.uuid4().hex
            payload["OperationId"] = operation_id
            # 变更是否已经在目标系统生效无法从超时判断，因此禁止自动重试。
            retries = 0
        else:
            retries = max(0, max_retries)

        # 唯一控制目标契约：进入 TiaWorker 子进程的工程路径/设备 IP 只能指向
        # config.yaml 的 target 节；调用方提供的路径/IP 不能旁路覆盖隔离目标。
        try:
            target = get_control_target()
        except Exception as exc:
            return make_error("EXEC_ERROR", f"控制目标校验失败，拒绝运行 TiaWorker: {exc}")
        payload["ProjectPath"] = str(target.project_path)
        for ip_key in ("Ip", "ip", "IP", "TargetIp", "target_ip", "plc_ip"):
            supplied_ip = payload.get(ip_key)
            if supplied_ip:
                try:
                    # 复用本请求已校验的 target，避免每个非空 IP 键都重新触发
                    # 完整 validate_control_target()（多个 IP 键时 N+1 次重复校验）。
                    require_control_ip(str(supplied_ip), target)
                except Exception as exc:
                    return make_error("EXEC_ERROR", f"拒绝非唯一控制目标 IP: {exc}")

        # 变更载荷写入独立临时目录，避免与其他进程混放在系统 %TEMP%；
        # 序列化与清理都纳入 try/finally，序列化失败不再泄漏临时文件。
        tmp_path: Optional[str] = None
        tmp_dir: Optional[str] = None
        tmp_file = None
        try:
            tmp_dir = tempfile.mkdtemp(prefix="tiaworker-")
            tmp_file = tempfile.NamedTemporaryFile(
                mode='w', suffix='.json', delete=False, encoding='utf-8', dir=tmp_dir
            )
            tmp_path = tmp_file.name
            json.dump(payload, tmp_file)
            tmp_file.close()
            tmp_file = None

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
                        timeout=actual_timeout,
                    )
                    out = _decode_worker_output(r.stdout).strip()
                    if out:
                        try:
                            result = json.loads(out)
                        except json.JSONDecodeError:
                            detail = f"rc={r.returncode}, out={out[:200]}"
                            if is_mutating:
                                return self._outcome_unknown(
                                    command, operation_id,
                                    f"无法解析 TiaWorker 输出: {detail}",
                                )
                            last_error = make_error("JSON_DECODE", detail)
                            if attempt < retries:
                                continue
                            return last_error
                        if not isinstance(result, dict):
                            detail = f"rc={r.returncode}, 非对象 JSON: {out[:200]}"
                            if is_mutating:
                                return self._outcome_unknown(command, operation_id, detail)
                            last_error = make_error("JSON_DECODE", detail)
                            if attempt < retries:
                                continue
                            return last_error
                        if result.get('ok') is True and r.returncode == 0:
                            response = {
                                "success": True,
                                "data": result.get('result', {}),
                                "raw": out,
                            }
                            if is_mutating:
                                response["operation_id"] = operation_id
                            return response
                        err_msg = result.get('error', '')
                        if not err_msg and r.returncode:
                            err_msg = f"TiaWorker 返回码 {r.returncode}"
                        if is_mutating:
                            return make_error("EXEC_ERROR", err_msg, operation_id=operation_id)
                        last_error = make_error("EXEC_ERROR", err_msg)
                        if attempt < retries:
                            continue
                        return last_error
                    # TiaWorker 无输出：保留退出码与 stderr，避免排障信息丢失。
                    no_output_detail = f"TiaWorker 无输出, rc={r.returncode}"
                    stderr = _decode_worker_output(r.stderr).strip()
                    if stderr:
                        no_output_detail += f", stderr={stderr[:200]}"
                    if is_mutating:
                        return self._outcome_unknown(command, operation_id, no_output_detail)
                    last_error = make_error("NO_OUTPUT", no_output_detail)
                    if attempt < retries:
                        continue
                    return last_error
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
                except OSError as e:
                    # 子进程未启动（exe 缺失/权限不足）：变更一定未发生，
                    # 报执行错误而不是结果未知，也不回传任意异常字符串。
                    return make_error("EXEC_ERROR", f"启动 TiaWorker 失败: {e}")
            return last_error or make_error("UNKNOWN")
        except Exception as exc:
            # 载荷准备步骤（mkdtemp / NamedTemporaryFile / json.dump）失败时，
            # 与其他失败路径一致返回错误 dict，而不是把原始异常抛给调用方；
            # finally 仍负责清理已创建的临时目录/文件。
            return make_error("EXEC_ERROR", f"TiaWorker 载荷准备失败: {exc}")
        finally:
            if tmp_file is not None:
                try:
                    tmp_file.close()
                except Exception:
                    pass
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError as exc:
                    warnings.warn(f"清理 TiaWorker 临时文件失败: {tmp_path}: {exc}")
            if tmp_dir:
                try:
                    os.rmdir(tmp_dir)
                except OSError:
                    pass
    # 这些命令可能修改工程、设备或连接状态。它们绝不能在超时后自动重试。
    MUTATING_COMMANDS = frozenset({
        "import-scl", "import-scl-replace", "create-lad", "download", "download-gui",
        "create-block", "import-block", "save-project", "add-tag", "delete-tag",
        "create-tag-table", "delete-tag-table", "delete-block", "create-db", "delete-db",
        "create-udt", "delete-udt", "create-watch-table", "delete-watch-table",
        "create-project", "archive-project", "go-online", "go-offline",
    })

    # 明确只读的命令白名单。不在白名单内的命令一律按变更处理（fail-closed）：
    # 注入 OperationId、结果未知时返回 OUTCOME_UNKNOWN 且禁止自动重试，
    # 防止漏列或新增的变更命令在结果未知时被自动重试。
    READONLY_COMMANDS = frozenset({
        "list-blocks", "list-dbs", "list-tags", "get-tags", "search-tag",
        "list-udts", "list-devices", "list-watch-tables",
        "get-project-info", "get-plc-status", "get-block-interface",
        "get-block-details", "get-device-config", "get-rack-slot",
        "get-compiler-errors", "check-consistency",
        "find-unused-blocks", "find-callers",
        "export-block", "export-tags-csv", "export-all-xml",
    })
