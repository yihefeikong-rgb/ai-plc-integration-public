"""共享辅助函数、路径、配置和 MCP 实例"""
import sys
import os
import subprocess
import json
import tempfile
import time
import secrets
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
P3_SCRIPT = SCRIPTS_DIR / "p3_flow.py"

# ── 配置 ──
# 追加到 sys.path 尾部，避免覆盖标准库同名模块
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))
if str(TIA_MCP_DIR) not in sys.path:
    sys.path.append(str(TIA_MCP_DIR))
try:
    from config_loader import cfg, validate_control_target
    _target = validate_control_target()
    PROJECT_PATH = str(_target.project_path)
    PLC_IP = _target.plc_ip
    PLCSIM_INSTANCE = _target.plcsim_instance
    GOLDEN_ZIP = cfg.simulation.golden_backup.zip_path
    STORAGE_PATH = cfg.simulation.golden_backup.storage_path
except Exception as e:
    raise RuntimeError(
        f"无法加载 TIA 配置文件 (mcp-servers/tia-mcp/config.yaml): {e}\n"
        "请检查 config.yaml 是否存在，以及 .env 中的环境变量是否正确配置"
    )


# ── 辅助函数 ──

def _run_python(script: Path, args: list[str], timeout: int = 60) -> dict:
    """运行 Python 脚本子进程，始终返回统一信封（success/output/stderr/returncode）。

    stdout 可解析为 JSON dict 时仅并入白名单键（data/error），success 语义以
    解析结果为准（未显式 success 视为失败，fail-closed）；非 dict JSON 放入
    data 键。保证所有调用方的 result.get(...) 结构一致，不会因 stdout 恰好是
    JSON 而返回不同结构，也不允许子进程输出覆盖信封字段。
    """
    cmd = [sys.executable, str(script)] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding='utf-8', errors='replace')
        out = r.stdout.strip()
        err = r.stderr.strip()
        result = {
            "success": r.returncode == 0,
            "output": out,
            "stderr": err,
            "returncode": r.returncode,
        }
        if out:
            try:
                parsed = json.loads(out)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                # 仅并入白名单键（data/error），避免子进程 stdout 覆盖信封字段
                # （output/stderr/returncode）；未显式 success 视为失败（fail-closed）
                for key in ("data", "error"):
                    if key in parsed:
                        result[key] = parsed[key]
                result["success"] = r.returncode == 0 and bool(parsed.get("success", False))
            elif parsed is not None:
                result["data"] = parsed
        if not result["success"]:
            result.setdefault("error", err or out)
        return result
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "stderr": "", "returncode": None, "error": f"超时 ({timeout}s)"}
    except Exception as e:
        return {"success": False, "output": "", "stderr": "", "returncode": None, "error": str(e)}


# ── 错误码和 TiaWorker 客户端（从共享层导入） ──
from mcp_common.tiaworker_client import (
    ERR_CODES, ERR_MSGS, make_error as _make_error, TiaWorkerClient,
)

# 全局 TiaWorker 客户端实例
_tia_version = getattr(cfg.tia, 'version', None) if cfg else None
_tiaworker_client = TiaWorkerClient(
    exe_path=TIAWORKER_EXE,
    tia_version=_tia_version,
)

# ── 审计日志（强制，HMAC 链式）：与 tools_blocks.py 直接路径共用同一审计链 ──
from mcp_common.audit import get_audit_logger, AuditConfigurationError, AuditStorageError

_audit = get_audit_logger()


def _run_tiaworker(command: str, data: dict, timeout: int = 180, tia_version: str | None = None, max_retries: int = 1, dry_run: bool = False) -> dict:
    """运行 TiaWorker.exe 子进程，带超时重试（委托给共享客户端）"""
    global _tiaworker_client
    if _tiaworker_client.exe_path != Path(TIAWORKER_EXE):
        _tiaworker_client = TiaWorkerClient(
            exe_path=TIAWORKER_EXE,
            tia_version=tia_version or _tia_version,
        )
    return _tiaworker_client.run(
        command=command,
        data=data,
        timeout=timeout,
        max_retries=max_retries,
        dry_run=dry_run,
    )


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
        # 仅在达到容量上限时做过期驱逐，避免每次写入都全量扫描
        if len(self._store) >= self._max_size:
            self._evict_expired()
            if len(self._store) >= self._max_size:
                oldest_key = min(self._store, key=lambda k: self._store[k]["timestamp"])
                del self._store[oldest_key]
        self._store[token] = data

    def pop(self, token: str) -> dict | None:
        # O(1) 取回并单独校验 TTL，避免每次取回都全量扫描
        entry = self._store.get(token)
        if entry is not None and time.time() - entry["timestamp"] > self._ttl:
            del self._store[token]
            return None
        return self._store.pop(token, None)

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [k for k, v in self._store.items() if now - v["timestamp"] > self._ttl]
        for k in expired:
            del self._store[k]

    def __len__(self) -> int:
        return len(self._store)


_preview_store = _PreviewStore()


def _audit_gate(operation: str, target: str, params: dict) -> str | None:
    """破坏性操作执行前的审计闸门（fail-closed）：审计不可用或主体未认证时拒绝执行。

    与 tools_blocks.py 直接路径一致：MCP 尚无已认证会话上下文，空主体使
    生产控制动作被拒绝，保证 preview→apply 不绕过 HMAC 审计链。
    """
    try:
        _audit.begin_control_operation(operation, target, "", params)
    except (AuditConfigurationError, AuditStorageError) as exc:
        return f"🚫 操作被拒绝: {exc}"
    return None


def _audit_outcome(operation: str, target: str, success: bool, detail: str, operator: str = "") -> str:
    """记录破坏性操作结果审计；写入失败返回告警后缀，不掩盖已发生的副作用。"""
    try:
        _audit.log(operation, target, "", operator=operator, success=success, detail=detail)
    except (AuditStorageError, OSError) as exc:
        return f" ⚠ 结果审计写入失败: {exc}"
    return ""


def _preview_action(action: str, params: dict) -> dict:
    """生成预览 token（CSPRNG 256 位，不可预测），缓存操作信息"""
    token = secrets.token_urlsafe(32)
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
    """验证 token 并返回缓存的操作信息（一次性、TTL 60 秒）

    缓存条目结构异常时 fail-closed 拒绝执行，绝不猜测执行意图。
    """
    entry = _preview_store.pop(token)
    if entry is None:
        return {"success": False, "error": "Token 无效或已过期"}
    action = entry.get("action")
    params = entry.get("params")
    if not isinstance(action, str) or not isinstance(params, dict):
        return {"success": False, "error": "Token 内容异常，已拒绝执行"}
    return {"success": True, "action": action, "params": params}


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

    # 审计闸门（fail-closed）：与 tools_blocks.py 直接路径一致；空主体在
    # 显式生产环境中被拒绝，保证 preview→apply 不绕过 HMAC 审计链
    operation = f"plc_apply.{action}"
    target = params.get("BlockName") or params.get("DbName") or params.get("FilePath") or action
    if msg := _audit_gate(operation, target, params):
        return msg

    # 重新调用 TiaWorker 执行
    tia_result = _run_tiaworker(action, params)
    if tia_result.get("success"):
        data = tia_result.get("data", {})
        warn = _audit_outcome(operation, target, True,
                              f"action={action} result={json.dumps(data, ensure_ascii=False)[:500]}")
        return f"✅ 操作成功 (action: {action})\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```{warn}"
    _audit_outcome(operation, target, False, f"action={action} error={tia_result.get('error', '')}")
    return f"❌ 操作失败: {tia_result.get('error', '未知错误')}"
