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
}


def make_error(code_key: str, detail: str = "") -> dict:
    """构造带错误码的结构化错误响应"""
    msg = ERR_MSGS.get(code_key, ERR_MSGS["UNKNOWN"])
    err_str = f"[{ERR_CODES.get(code_key, ERR_CODES['UNKNOWN'])}] {msg}"
    if detail:
        err_str += f": {detail}"
    return {"success": False, "error": err_str, "error_code": code_key}


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

    def run(
        self,
        command: str,
        data: dict,
        timeout: Optional[int] = None,
        max_retries: int = 1,
        dry_run: bool = False,
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

        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8'
        )
        json.dump(data, tmp)
        tmp_path = tmp.name
        tmp.close()

        try:
            last_error = None
            for attempt in range(1 + max_retries):
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
                            if result.get('ok') is True:
                                return {
                                    "success": True,
                                    "data": result.get('result', {}),
                                    "raw": out,
                                }
                            else:
                                err_msg = result.get('error', '')
                                return make_error("EXEC_ERROR", err_msg)
                        except json.JSONDecodeError:
                            return make_error(
                                "JSON_DECODE",
                                f"rc={r.returncode}, out={out[:200]}",
                            )
                    return make_error("NO_OUTPUT")
                except subprocess.TimeoutExpired:
                    last_error = make_error(
                        "TIMEOUT",
                        f"尝试 {attempt+1}/{1+max_retries}, 超时 {actual_timeout}s",
                    )
                    if attempt < max_retries:
                        continue
                    return last_error
                except Exception as e:
                    return make_error("EXEC_ERROR", str(e))
            return last_error or make_error("UNKNOWN")
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
