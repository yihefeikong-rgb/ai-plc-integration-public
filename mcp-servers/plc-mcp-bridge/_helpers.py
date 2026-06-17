"""共享辅助函数、路径、配置和 MCP 实例"""
import sys
import os
import subprocess
import json
import tempfile
import time
import uuid
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# ── MCP 实例 ──
mcp = FastMCP("plc_mcp")

# ── 路径 ──
PROJECT_ROOT = Path(__file__).parent.parent.parent
TIA_MCP_DIR = PROJECT_ROOT / "mcp-servers" / "tia-mcp"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

PLCSIM_API = TIA_MCP_DIR / "plcsim_api.py"
TIAWORKER_EXE = TIA_MCP_DIR / "bin" / "TiaWorker.exe"
DOWNLOAD_SCRIPT = TIA_MCP_DIR / "download_to_plcsim.py"
P3_SCRIPT = PROJECT_ROOT / "p3_flow.py"

# ── 配置 ──
# 追加到 sys.path 尾部，避免覆盖标准库同名模块
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))
if str(TIA_MCP_DIR) not in sys.path:
    sys.path.append(str(TIA_MCP_DIR))
try:
    from config_loader import cfg
    PROJECT_PATH = cfg.tia.project_path
    PLC_IP = cfg.simulation.advanced.plc_ip
    PLCSIM_INSTANCE = cfg.factory_io.plcsim_instance
    GOLDEN_ZIP = os.path.join(os.path.dirname(PROJECT_PATH), 'factory_io1_golden.zip')
    STORAGE_PATH = os.path.join(os.path.dirname(PROJECT_PATH), 'plcsim_storage')
except Exception:
    cfg = None
    PROJECT_PATH = ""
    PLC_IP = "192.168.0.1"
    PLCSIM_INSTANCE = "factoryio"
    GOLDEN_ZIP = ""
    STORAGE_PATH = ""


# ── 辅助函数 ──

def _run_python(script: Path, args: list[str], timeout: int = 60) -> dict:
    """运行 Python 脚本子进程，返回解析后的 JSON"""
    cmd = [sys.executable, str(script)] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding='utf-8', errors='replace')
        out = r.stdout.strip()
        err = r.stderr.strip()
        if out:
            try:
                return json.loads(out)
            except json.JSONDecodeError:
                pass
        return {
            "success": r.returncode == 0,
            "output": out,
            "stderr": err,
            "returncode": r.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"超时 ({timeout}s)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


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


def _make_error(code_key: str, detail: str = "") -> dict:
    """构造带错误码的结构化错误响应"""
    msg = ERR_MSGS.get(code_key, ERR_MSGS["UNKNOWN"])
    err_str = f"[{ERR_CODES.get(code_key, ERR_CODES['UNKNOWN'])}] {msg}"
    if detail:
        err_str += f": {detail}"
    return {"success": False, "error": err_str, "error_code": code_key}


def _run_tiaworker(command: str, data: dict, timeout: int = 180, tia_version: str | None = None, max_retries: int = 1, dry_run: bool = False) -> dict:
    """运行 TiaWorker.exe 子进程，带超时重试"""
    if not TIAWORKER_EXE.exists():
        return _make_error("NOT_COMPILED", str(TIAWORKER_EXE))

    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
    json.dump(data, tmp)
    tmp_path = tmp.name
    tmp.close()

    try:
        last_error = None
        for attempt in range(1 + max_retries):
            try:
                cmd = [str(TIAWORKER_EXE)]
                if dry_run:
                    cmd.append("--dry-run")
                tia_ver = tia_version or getattr(cfg.tia, 'version', None) if cfg else None
                if tia_ver:
                    cmd.extend([f"--tia-major-version={tia_ver}"])
                cmd.extend([command, tmp_path])
                r = subprocess.run(
                    cmd,
                    capture_output=True, text=True, timeout=timeout,
                    encoding='utf-8', errors='replace',
                )
                out = r.stdout.strip()
                if out:
                    try:
                        result = json.loads(out)
                        if result.get('ok') is True:
                            return {"success": True, "data": result.get('result', {}), "raw": out}
                        else:
                            err_msg = result.get('error', '')
                            return _make_error("EXEC_ERROR", err_msg)
                    except json.JSONDecodeError:
                        return _make_error("JSON_DECODE", f"rc={r.returncode}, out={out[:200]}")
                return _make_error("NO_OUTPUT")
            except subprocess.TimeoutExpired:
                last_error = _make_error("TIMEOUT", f"尝试 {attempt+1}/{1+max_retries}, 超时 {timeout}s")
                if attempt < max_retries:
                    continue
                return last_error
            except Exception as e:
                return _make_error("EXEC_ERROR", str(e))
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def _format_result(success: bool, data=None, error: str = "") -> str:
    """统一格式化返回消息"""
    if success:
        if data:
            return f"✅ 成功\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```"
        return "✅ 成功"
    return f"❌ 失败: {error}"


def _check_project() -> str | None:
    """检查项目路径，返回错误信息或 None"""
    if not PROJECT_PATH or not os.path.exists(PROJECT_PATH):
        return f"❌ 项目文件不存在: {PROJECT_PATH}"
    return None


def _dry_run_msg(action: str, params: dict) -> str:
    """dry-run 模式下的预览消息"""
    return f"🔍 [Dry-Run] 将执行: {action}\n```json\n{json.dumps(params, ensure_ascii=False, indent=2)}\n```"


def _handle_preview_or_dry_run(action: str, params: dict, dry_run: bool, preview: bool) -> str | None:
    """统一处理 dry-run 和 preview 模式。返回 None 表示需要继续实际执行。"""
    if dry_run:
        return _dry_run_msg(action, params)
    if preview:
        r = _preview_action(action, params)
        return f"🔍 预览:\n```json\n{json.dumps(r['preview'], ensure_ascii=False, indent=2)}\n```\nToken: `{r['token']}`\n使用 `plc_apply(token=\"{r['token']}\")` 执行"
    return None


# ── Preview-Then-Apply 安全模式 ──

_PREVIEW_TTL = 60  # token 有效期（秒）
_PREVIEW_MAX_SIZE = 200  # 最大缓存数量


class _PreviewStore:
    """带容量限制和 TTL 自动清理的预览缓存"""

    def __init__(self, max_size: int = _PREVIEW_MAX_SIZE, ttl: int = _PREVIEW_TTL):
        self._store: dict[str, dict] = {}
        self._max_size = max_size
        self._ttl = ttl

    def put(self, token: str, data: dict) -> None:
        self._evict_expired()
        if len(self._store) >= self._max_size:
            oldest_key = min(self._store, key=lambda k: self._store[k]["timestamp"])
            del self._store[oldest_key]
        self._store[token] = data

    def pop(self, token: str) -> dict | None:
        self._evict_expired()
        return self._store.pop(token, None)

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [k for k, v in self._store.items() if now - v["timestamp"] > self._ttl]
        for k in expired:
            del self._store[k]

    def __len__(self) -> int:
        return len(self._store)


_preview_store = _PreviewStore()


def _preview_action(action: str, params: dict) -> dict:
    """生成预览 token，缓存操作信息"""
    token = uuid.uuid4().hex
    _preview_store.put(token, {
        "action": action,
        "params": params,
        "timestamp": time.time(),
    })
    return {
        "success": True,
        "preview": {"action": action, "params": params},
        "token": token,
    }


def _apply_preview(token: str) -> dict:
    """验证 token 并返回缓存的操作信息（_PreviewStore.pop 已包含 TTL 清理）"""
    entry = _preview_store.pop(token)
    if entry is None:
        return {"success": False, "error": "Token 无效或已过期"}
    return {"success": True, "action": entry["action"], "params": entry["params"]}


@mcp.tool(name="plc_apply", annotations={"destructiveHint": True})
async def plc_apply(token: str) -> str:
    """执行之前预览过的操作（需要从 preview 返回的 token）

    Args:
        token: preview 步骤返回的 token
    """
    result = _apply_preview(token)
    if not result.get("success"):
        return f"❌ 执行失败: {result.get('error', '未知错误')}"

    action = result["action"]
    params = result["params"]

    # 重新调用 TiaWorker 执行
    tia_result = _run_tiaworker(action, params)
    if tia_result.get("success"):
        data = tia_result.get("data", {})
        return f"✅ 操作成功 (action: {action})\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```"
    return f"❌ 操作失败: {tia_result.get('error', '未知错误')}"
