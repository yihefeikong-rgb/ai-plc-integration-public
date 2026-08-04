"""
TiaCommander Provider — 外部闭源 TIA 后端适配器

通过 MCP stdio 协议与 TiaCommander.exe 通信，实现 TiaProvider 接口。
TiaCommander 是外部专有软件，需单独获取授权。
"""
from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from plc_gateway.providers.base import ProviderResult, TiaProvider

_logger = logging.getLogger(__name__)

# MCP 协议版本
_MCP_PROTOCOL_VERSION = "2025-11-25"

# 单个 JSON-RPC 请求的响应超时（秒）
_RESPONSE_TIMEOUT = 30.0

# stdout 读线程 EOF 哨兵
_EOF_SENTINEL = object()

# 受控 Apply 允许的操作（与 workflows/guarded_apply._ALLOWED_OPERATIONS、
# workflows/network_patch._SUPPORTED_OPERATIONS 保持一致；Provider 层独立 fail-closed）
_ALLOWED_PATCH_OPERATIONS = frozenset([
    "update_network_title",
    "update_network_comment",
])

# 禁止修改的受保护块（与 workflows/guarded_apply._PROTECTED_BLOCKS 保持一致）
_PROTECTED_PATCH_BLOCKS = frozenset(["OB1", "OB100", "OB121", "OB122"])


class McpStdioClient:
    """MCP stdio 客户端 — 通过子进程与 MCP 服务器通信

    可靠性设计：
    - stdout/stderr 各由独立后台线程持续消费，主线程不会被阻塞 readline 卡住；
    - 响应按 JSON-RPC id 匹配，通知与迟到响应被忽略，避免协议错位；
    - 子进程退出（EOF）立即上报，超时由单调时钟保证生效；
    - stderr 持续排空，避免管道写满阻塞子进程。
    """

    def __init__(self, exe_path: str | Path, cwd: str | Path | None = None):
        self._exe = Path(exe_path)
        self._cwd = Path(cwd) if cwd else self._exe.parent
        self._process: subprocess.Popen | None = None
        self._next_id = 1
        self._id_lock = threading.Lock()
        self._messages: queue.Queue = queue.Queue()
        self._stdout_reader: threading.Thread | None = None
        self._stderr_reader: threading.Thread | None = None
        self._stderr_lines: list[str] = []
        self._stderr_lock = threading.Lock()

    # ── 子进程与读线程管理 ──

    def _start(self) -> None:
        """启动 TiaCommander 子进程并开启 stdout/stderr 读线程"""
        self._process = subprocess.Popen(
            [str(self._exe)],
            cwd=str(self._cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
        )
        process = self._process
        self._stdout_reader = threading.Thread(
            target=self._read_stdout, args=(process,),
            name="tiacommander-stdout", daemon=True)
        self._stderr_reader = threading.Thread(
            target=self._read_stderr, args=(process,),
            name="tiacommander-stderr", daemon=True)
        self._stdout_reader.start()
        self._stderr_reader.start()

    def _read_stdout(self, process: subprocess.Popen) -> None:
        """后台读线程：持续读取 stdout，将 JSON 消息放入队列"""
        while True:
            line = process.stdout.readline()
            if line == "":
                break
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                _logger.debug(f"忽略无法解析的 TiaCommander 输出: {line[:200]}")
                continue
            self._messages.put(msg)
        self._messages.put(_EOF_SENTINEL)

    def _read_stderr(self, process: subprocess.Popen) -> None:
        """后台读线程：持续排空 stderr，避免管道写满阻塞子进程"""
        while True:
            line = process.stderr.readline()
            if line == "":
                break
            if line.strip():
                _logger.warning(f"TiaCommander stderr: {line.rstrip()}")
                with self._stderr_lock:
                    self._stderr_lines.append(line.rstrip())
                    if len(self._stderr_lines) > 50:
                        del self._stderr_lines[0]

    def _tail_stderr(self) -> str:
        """返回 stderr 最近若干行（用于错误诊断）"""
        with self._stderr_lock:
            return "\n".join(self._stderr_lines[-10:])

    # ── JSON-RPC 收发 ──

    def _send(self, method: str, params: dict | None = None) -> dict:
        """发送 JSON-RPC 请求并等待响应

        - 响应必须携带与请求相同的 id；通知（无 id）与迟到响应被忽略；
        - 子进程退出或超时立即抛 RuntimeError，不会无限挂起。
        """
        if self._process is None:
            raise RuntimeError("MCP 客户端未连接")

        with self._id_lock:
            req_id = self._next_id
            self._next_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }
        if params is not None:
            request["params"] = params

        payload = json.dumps(request) + "\n"
        _logger.debug(f"TiaCommander << {payload.strip()[:200]}")

        try:
            self._process.stdin.write(payload)
            self._process.stdin.flush()
        except Exception as e:
            raise RuntimeError(f"写入 MCP 请求失败: {e}")

        # 读取响应（按请求 id 匹配）
        deadline = time.monotonic() + _RESPONSE_TIMEOUT
        response = None
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("MCP 响应超时")
            try:
                msg = self._messages.get(timeout=remaining)
            except queue.Empty:
                raise RuntimeError("MCP 响应超时")
            if msg is _EOF_SENTINEL:
                tail = self._tail_stderr()
                detail = f"，stderr 尾部: {tail}" if tail else ""
                raise RuntimeError(f"MCP 子进程已退出（stdout 关闭）{detail}")
            if msg.get("id") is None:
                continue  # JSON-RPC 通知，不是本请求的响应
            if msg.get("id") != req_id:
                _logger.debug(f"忽略 id 不匹配的响应: {msg.get('id')}")
                continue  # 迟到/错位响应，继续等待本请求的响应
            response = msg
            break

        _logger.debug(f"TiaCommander >> {json.dumps(response)[:200]}")

        # 检查 JSON-RPC 错误
        if "error" in response and response["error"] is not None:
            err = response["error"]
            raise RuntimeError(f"MCP 错误: {err.get('message', str(err))}")

        return response

    def _notify(self, method: str, params: dict | None = None) -> None:
        """发送 JSON-RPC 通知（无 id，不等待响应）"""
        if self._process is None:
            raise RuntimeError("MCP 客户端未连接")
        request = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            request["params"] = params
        payload = json.dumps(request) + "\n"
        _logger.debug(f"TiaCommander << {payload.strip()[:200]}")
        try:
            self._process.stdin.write(payload)
            self._process.stdin.flush()
        except Exception as e:
            raise RuntimeError(f"写入 MCP 通知失败: {e}")

    def connect(self) -> dict:
        """初始化 MCP 连接

        initialize 成功后发送 notifications/initialized；
        任一步骤失败都会回收子进程，避免进程泄漏。
        """
        _logger.info(f"启动 TiaCommander: {self._exe}")
        try:
            self._start()
            result = self._send("initialize", {
                "protocolVersion": _MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "plc-gateway",
                    "version": "1.0",
                },
            })
            self._notify("notifications/initialized")
            return result.get("result", {})
        except Exception:
            self.disconnect()
            raise

    def list_tools(self) -> list[dict]:
        """列出所有可用工具"""
        result = self._send("tools/list")
        return result.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        """调用 MCP 工具

        返回 tools/call 的 result（含 content/isError），由调用方判定成败。
        """
        result = self._send("tools/call", {
            "name": name,
            "arguments": arguments or {},
        })
        return result.get("result", {})

    def disconnect(self) -> None:
        """断开 MCP 连接并回收子进程与读线程"""
        process = self._process
        self._process = None
        if process:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        # 读线程在管道 EOF 后自行退出；等待回收，避免线程泄漏
        for thread in (self._stdout_reader, self._stderr_reader):
            if thread is not None and thread.is_alive():
                thread.join(timeout=5)
        self._stdout_reader = None
        self._stderr_reader = None
        # 丢弃队列中的迟到消息
        while True:
            try:
                self._messages.get_nowait()
            except queue.Empty:
                break


class TiaCommanderProvider(TiaProvider):
    """TiaCommander 提供者 — 通过 MCP stdio 调用外部 TiaCommander.exe"""

    def __init__(self, exe_path: str | Path, cwd: str | Path | None = None,
                 read_only: bool = True):
        self._exe = Path(exe_path)
        self._cwd = Path(cwd) if cwd else self._exe.parent
        self._client: McpStdioClient | None = None
        self._connected = False
        self._read_only = read_only

    @property
    def name(self) -> str:
        return "tiacommander"

    @property
    def available(self) -> bool:
        return self._exe.exists()

    @property
    def read_only(self) -> bool:
        return self._read_only

    def _check_read_only(self, operation: str) -> ProviderResult | None:
        """检查是否只读模式，如果是则拒绝写操作"""
        if self._read_only:
            _logger.warning(f"只读模式下拒绝写操作: {operation}")
            return ProviderResult(
                ok=False, operation=operation,
                error=f"TiaCommander 处于只读模式，拒绝操作: {operation}",
            )
        return None

    def _ensure_connected(self) -> McpStdioClient:
        """确保已连接，返回客户端实例

        连接失败时清理子进程并保持 _connected=False（fail-closed）。
        """
        if self._client is not None and self._connected:
            return self._client
        client = McpStdioClient(self._exe, self._cwd)
        try:
            client.connect()
        except Exception:
            client.disconnect()
            self._client = None
            self._connected = False
            raise
        self._client = client
        self._connected = True
        return self._client

    def _sanitize_error(self, exc: object) -> str:
        """对异常/错误信息脱敏，避免泄露 exe 绝对路径等本地路径"""
        message = str(exc)
        exe = str(self._exe)
        if exe and exe in message:
            message = message.replace(exe, "TiaCommander.exe")
        cwd = str(self._cwd)
        if cwd and cwd in message:
            message = message.replace(cwd, "<tiacommander-dir>")
        return message

    def _call(self, tool: str, action: str, **kwargs) -> ProviderResult:
        """调用 TiaCommander 工具并包装为 ProviderResult

        fail-closed：
        - MCP tools/call 返回 isError=true 时按失败处理；
        - 文本内容中显式 success=false 的 JSON 按失败处理；
        - 异常信息脱敏，不泄露本地路径。
        """
        try:
            client = self._ensure_connected()
            result = client.call_tool(tool, {"action": action, **kwargs})
            # 从 MCP 响应中提取文本内容
            content = result.get("content", [])
            text = ""
            for item in content:
                if item.get("type") == "text":
                    text = item.get("text", "")
                    break
            # MCP 工具级错误（isError）必须按失败处理
            if result.get("isError"):
                return ProviderResult(
                    ok=False,
                    operation=f"tiacommander.{tool}.{action}",
                    provider="tiacommander",
                    error=self._sanitize_error(
                        f"TiaCommander {tool}/{action} 失败: {text or '未知错误'}"),
                )
            # 尝试解析 JSON
            parsed = None
            if text:
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    parsed = {"text": text}
            # 显式失败标记（success=false）按失败处理
            if isinstance(parsed, dict) and parsed.get("success") is False:
                detail = parsed.get("error") or parsed.get("message") or "TiaCommander 调用失败"
                return ProviderResult(
                    ok=False,
                    operation=f"tiacommander.{tool}.{action}",
                    provider="tiacommander",
                    error=self._sanitize_error(detail),
                )
            return ProviderResult(
                ok=True,
                operation=f"tiacommander.{tool}.{action}",
                provider="tiacommander",
                result=parsed or {"text": text},
            )
        except Exception as e:
            return ProviderResult(
                ok=False,
                operation=f"tiacommander.{tool}.{action}",
                provider="tiacommander",
                error=self._sanitize_error(e),
            )

    def disconnect(self) -> None:
        """断开连接"""
        if self._client:
            self._client.disconnect()
            self._client = None
            self._connected = False

    # ── TiaProvider 接口实现 ──

    def get_project_info(self) -> ProviderResult:
        return self._call("session", "get_project")

    def list_blocks(self) -> ProviderResult:
        return self._call("blocks_read", "list")

    def get_block_xml(self, block_name: str) -> ProviderResult:
        return self._call("blocks_read", "get_xml_raw", blockName=block_name)

    def get_block_interface(self, block_name: str) -> ProviderResult:
        return self._call("blocks_read", "get_interface", blockName=block_name)

    def compile_project(self) -> ProviderResult:
        return self._call("blocks_read", "compile_all")

    def list_devices(self) -> ProviderResult:
        return self._call("session", "list_devices")

    def create_block(self, block_name: str, lang: str = "SCL") -> ProviderResult:
        blocked = self._check_read_only("tiacommander.create_block")
        if blocked:
            return blocked
        return self._call("blocks_write", "create_block",
                          blockName=block_name, language=lang)

    def import_block_xml(self, xml_path: str) -> ProviderResult:
        blocked = self._check_read_only("tiacommander.import_block_xml")
        if blocked:
            return blocked
        return self._call("blocks_write", "import_xml_file", filePath=xml_path)

    def delete_block(self, block_name: str) -> ProviderResult:
        blocked = self._check_read_only("tiacommander.delete_block")
        if blocked:
            return blocked
        return self._call("blocks_write", "delete_block", blockName=block_name)

    def preview_patch(self, patch: dict) -> ProviderResult:
        """预览网络级 Patch

        本 Provider 不提供真实预览能力：预览必须由 guarded_apply / network_patch
        工作流读取块 XML、计算 Hash 与 Diff 完成。直接调用此处视为未预览，fail-closed。
        """
        return ProviderResult.error_result(
            "tiacommander.preview_patch",
            "TiaCommander Provider 不直接提供预览；请通过 guarded_apply / network_patch "
            "工作流生成预览并人工确认后再执行",
            code="PREVIEW_REQUIRED",
            provider="tiacommander",
            status="blocked",
        )

    def apply_patch(self, patch: dict) -> ProviderResult:
        """应用网络级 Patch（利用 TiaCommander 的网络修改能力）

        Provider 层独立 fail-closed：
        - 操作类型白名单与 guarded_apply / network_patch 一致
          （仅 update_network_title / update_network_comment）；
        - 拒绝受保护块与缺失/无效 network_index；
        - 任一操作失败立即停止，避免部分应用。
        """
        blocked = self._check_read_only("tiacommander.apply_patch")
        if blocked:
            return blocked

        block = patch.get("block", "")
        if not isinstance(block, str) or not block.strip():
            return ProviderResult.error_result(
                "tiacommander.apply_patch",
                "patch 缺少有效的 block 字段",
                code="INVALID_PATCH",
                provider="tiacommander",
                status="blocked",
            )
        if block.upper() in _PROTECTED_PATCH_BLOCKS:
            return ProviderResult.error_result(
                "tiacommander.apply_patch",
                f"禁止修改受保护块: {block}",
                code="PROTECTED_BLOCK",
                provider="tiacommander",
                status="blocked",
            )

        operations = patch.get("operations", [])
        if not isinstance(operations, list) or not operations:
            return ProviderResult.error_result(
                "tiacommander.apply_patch",
                "patch 没有指定任何操作",
                code="INVALID_PATCH",
                provider="tiacommander",
                status="blocked",
            )

        results = []
        for i, op in enumerate(operations):
            if not isinstance(op, dict):
                r = ProviderResult.error_result(
                    "apply_patch", f"operations[{i}] 必须是 JSON 对象",
                    provider="tiacommander", status="blocked")
                results.append(r)
                break
            op_type = op.get("operation", "")
            net_idx = op.get("network_index")
            if op_type not in _ALLOWED_PATCH_OPERATIONS:
                r = ProviderResult.error_result(
                    "apply_patch",
                    f"operations[{i}]: 不支持的操作 '{op_type}'，"
                    f"仅允许: {', '.join(sorted(_ALLOWED_PATCH_OPERATIONS))}",
                    provider="tiacommander", status="blocked")
                results.append(r)
                break
            if net_idx is None:
                r = ProviderResult.error_result(
                    "apply_patch", f"operations[{i}]: 缺少必填字段 network_index",
                    provider="tiacommander", status="blocked")
                results.append(r)
                break
            if not isinstance(net_idx, int) or net_idx < 0:
                r = ProviderResult.error_result(
                    "apply_patch", f"operations[{i}]: network_index 必须是非负整数",
                    provider="tiacommander", status="blocked")
                results.append(r)
                break
            if op_type == "update_network_title":
                r = self._call("blocks_write", "update_network",
                               blockName=block, networkIndex=net_idx,
                               title=op.get("new_title", ""))
            else:  # update_network_comment
                r = self._call("blocks_write", "update_network",
                               blockName=block, networkIndex=net_idx,
                               comment=op.get("new_comment", ""))
            results.append(r)
            if not r.ok:
                # fail-fast：任一操作失败立即停止，避免部分应用
                break

        all_ok = all(r.ok for r in results)
        return ProviderResult(
            ok=all_ok, operation="tiacommander.apply_patch",
            result={"block": block, "operations": [r.to_dict() for r in results]},
        )


def create_provider(tiacommander_dir: str | Path | None = None) -> TiaCommanderProvider | None:
    """工厂函数：创建 TiaCommanderProvider

    Args:
        tiacommander_dir: TiaCommander 目录，默认从环境变量或常见路径读取

    Returns:
        TiaCommanderProvider 实例，如果找不到可执行文件则返回 None
    """
    if tiacommander_dir:
        exe = Path(tiacommander_dir) / "TiaCommander.exe"
    else:
        # 环境变量
        env_path = os.environ.get("TIA_COMMANDER_DIR", "")
        if env_path:
            exe = Path(env_path) / "TiaCommander.exe"
        else:
            # 本地开发路径
            exe = Path(__file__).parent.parent.parent / "tiacommander-mcp" / "TiaCommander.exe"

    if not exe.exists():
        return None
    return TiaCommanderProvider(exe, cwd=exe.parent)
