"""
TiaCommander Provider — 外部闭源 TIA 后端适配器

通过 MCP stdio 协议与 TiaCommander.exe 通信，实现 TiaProvider 接口。
TiaCommander 是外部专有软件，需单独获取授权。
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from plc_gateway.providers.base import ProviderResult, TiaProvider

_logger = logging.getLogger(__name__)

# MCP 协议版本
_MCP_PROTOCOL_VERSION = "2025-11-25"


class McpStdioClient:
    """MCP stdio 客户端 — 通过子进程与 MCP 服务器通信"""

    def __init__(self, exe_path: str | Path, cwd: str | Path | None = None):
        self._exe = Path(exe_path)
        self._cwd = Path(cwd) if cwd else self._exe.parent
        self._process: subprocess.Popen | None = None
        self._next_id = 1

    def _send(self, method: str, params: dict | None = None) -> dict:
        """发送 JSON-RPC 请求并等待响应"""
        if self._process is None:
            raise RuntimeError("MCP 客户端未连接")

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

        # 读取响应（逐行读取 JSON）
        response = None
        deadline = time.time() + 30
        while time.time() < deadline:
            line = self._process.stdout.readline()
            if not line:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                response = json.loads(line)
                break
            except json.JSONDecodeError:
                continue

        if response is None:
            raise RuntimeError("MCP 响应超时")

        _logger.debug(f"TiaCommander >> {json.dumps(response)[:200]}")

        # 检查错误
        if "error" in response and response["error"] is not None:
            err = response["error"]
            raise RuntimeError(f"MCP 错误: {err.get('message', str(err))}")

        return response

    def connect(self) -> dict:
        """初始化 MCP 连接"""
        _logger.info(f"启动 TiaCommander: {self._exe}")
        self._process = subprocess.Popen(
            [str(self._exe)],
            cwd=str(self._cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
        )

        # 发送 initialize
        result = self._send("initialize", {
            "protocolVersion": _MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {
                "name": "plc-gateway",
                "version": "1.0",
            },
        })
        return result.get("result", {})

    def list_tools(self) -> list[dict]:
        """列出所有可用工具"""
        result = self._send("tools/list")
        return result.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        """调用 MCP 工具"""
        result = self._send("tools/call", {
            "name": name,
            "arguments": arguments or {},
        })
        return result.get("result", {})

    def disconnect(self) -> None:
        """断开 MCP 连接"""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                self._process.kill()
            self._process = None


class TiaCommanderProvider(TiaProvider):
    """TiaCommander 提供者 — 通过 MCP stdio 调用外部 TiaCommander.exe"""

    def __init__(self, exe_path: str | Path, cwd: str | Path | None = None,
                 read_only: bool = True):
        self._exe = Path(exe_path)
        self._cwd = Path(cwd) if cwd else self._exe.parent
        self._client: McpStdioClient | None = None
        self._connected = False
        self._tool_cache: list[dict] = []
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
        """确保已连接，返回客户端实例"""
        if self._client is None or not self._connected:
            self._client = McpStdioClient(self._exe, self._cwd)
            self._client.connect()
            self._tool_cache = self._client.list_tools()
            self._connected = True
        return self._client

    def _call(self, tool: str, action: str, **kwargs) -> ProviderResult:
        """调用 TiaCommander 工具并包装为 ProviderResult"""
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
            # 尝试解析 JSON
            parsed = None
            if text:
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    parsed = {"text": text}
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
                error=str(e),
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
        # TiaCommander 支持直接网络级操作，无需单独的 preview_patch
        return ProviderResult(
            ok=True, operation="tiacommander.preview_patch",
            result={"note": "TiaCommander 直接执行网络操作，无需单独预览",
                    "patch": patch},
        )

    def apply_patch(self, patch: dict) -> ProviderResult:
        """应用网络级 Patch（利用 TiaCommander 的网络修改能力）"""
        blocked = self._check_read_only("tiacommander.apply_patch")
        if blocked:
            return blocked
        block = patch.get("block", "")
        operations = patch.get("operations", [])
        results = []
        for op in operations:
            op_type = op.get("operation", "")
            net_idx = op.get("network_index", 0)
            if op_type == "replace_network":
                r = self._call("blocks_write", "replace_network",
                               blockName=block, networkIndex=net_idx,
                               network=op.get("new_network", {}))
            elif op_type == "insert_network":
                r = self._call("blocks_write", "add_network",
                               blockName=block, networkIndex=net_idx,
                               network=op.get("new_network", {}))
            elif op_type == "delete_network":
                r = self._call("blocks_write", "delete_network",
                               blockName=block, networkIndex=net_idx)
            elif op_type == "update_metadata":
                r = self._call("blocks_write", "update_network",
                               blockName=block, networkIndex=net_idx,
                               title=op.get("new_title", ""),
                               comment=op.get("new_comment", ""))
            else:
                r = ProviderResult(ok=False, operation="apply_patch",
                                   error=f"不支持的操作: {op_type}")
            results.append(r)

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
