"""PLCSIM Advanced 管理工具"""
import json
import os
import re
import time
from _helpers import mcp, _run_python, _format_result
from _helpers import PLCSIM_API, GOLDEN_ZIP, STORAGE_PATH
from mcp_common.control_target import TargetConfigurationError, get_control_target, require_control_ip


def _resolve_target(name: str = "", ip: str = ""):
    """管理操作只能作用于唯一隔离 PLCSIM 实例。"""
    try:
        target = get_control_target()
        if name and name != target.plcsim_instance:
            raise TargetConfigurationError(
                f"PLCSIM 实例必须为 {target.plcsim_instance}，收到 {name}"
            )
        require_control_ip(ip or target.plc_ip)
        return target, ""
    except TargetConfigurationError as exc:
        return None, f"🚫 操作被拒绝: {exc}"


def _destructive_preview(action: str, params: dict) -> str:
    """破坏性操作确认闸门：未显式 confirm=True 时只返回预览，不执行。"""
    return (
        f"⚠️ 该操作具有破坏性，未执行。\n"
        f"操作: {action}\n"
        f"参数: {json.dumps(params, ensure_ascii=False, indent=2)}\n"
        f"确认后果后请携带 confirm=True 重新调用。"
    )


# ── PLCSIM 实例列表缓存（避免每次调用都启动新解释器子进程） ──
_INSTANCE_LIST_CACHE: dict = {}
_INSTANCE_LIST_CACHE_TTL = 5.0  # 秒

_INSTANCE_LINE_RE = re.compile(r"\[\s*(\d+)\s*\]\s+(\S+)\s*[—-]\s*(\S+)(?:\s+\(([^)]*)\))?")


def _list_instances() -> dict:
    """查询 PLCSIM 实例列表（短 TTL 缓存子进程结果，供 list/状态查询复用）"""
    now = time.monotonic()
    if _INSTANCE_LIST_CACHE and now - _INSTANCE_LIST_CACHE.get("ts", 0) < _INSTANCE_LIST_CACHE_TTL:
        return _INSTANCE_LIST_CACHE["result"]
    result = _run_python(PLCSIM_API, ["list"])
    _INSTANCE_LIST_CACHE.clear()
    _INSTANCE_LIST_CACHE.update({"ts": now, "result": result})
    return result


def _parse_instance_lines(output: str) -> list[dict]:
    """结构化解析 plcsim_api list 输出行: '[0] factoryio — RUN (1511)'"""
    entries = []
    for line in output.splitlines():
        m = _INSTANCE_LINE_RE.search(line)
        if m:
            entries.append({
                "id": m.group(1),
                "name": m.group(2),
                "state": m.group(3),
                "cpu": m.group(4) or "",
            })
    return entries


@mcp.tool(
    name="plc_list_instances",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
)
async def list_instances() -> str:
    """列出所有已注册的 PLCSIM Advanced 仿真实例"""
    result = _list_instances()
    if not result.get("success"):
        return _format_result(False, error=result.get("error") or result.get("output") or "查询失败")
    out = result.get("output", "")
    return f"当前 PLCSIM 实例:\n{out}" if out else "无运行实例"


@mcp.tool(
    name="plc_create_instance",
    annotations={"destructiveHint": False},
)
async def create_instance(
    name: str = "",
    ip: str = "",
    cpu_type: str = "1511",
) -> str:
    """创建并启动一个新的 PLCSIM Advanced 空壳实例"""
    target, error = _resolve_target(name, ip)
    if error:
        return error
    result = _run_python(
        PLCSIM_API,
        ["create", target.plcsim_instance, target.plc_ip, cpu_type],
        timeout=120,
    )
    return _format_result(result.get("success"), error=result.get("error", ""))


@mcp.tool(
    name="plc_stop_instance",
    annotations={"destructiveHint": True},
)
async def stop_instance(name: str = "", confirm: bool = False) -> str:
    """停止并删除指定 PLCSIM Advanced 实例

    破坏性操作：默认只返回预览，需 confirm=True 才执行。
    """
    target, error = _resolve_target(name)
    if error:
        return error
    if not confirm:
        return _destructive_preview("停止并删除 PLCSIM 实例", {"instance": target.plcsim_instance})
    result = _run_python(PLCSIM_API, ["stop", target.plcsim_instance], timeout=60)
    return _format_result(result.get("success"), error=result.get("error", ""))


@mcp.tool(
    name="plc_get_state",
    annotations={"readOnlyHint": True},
)
async def get_instance_state(name: str = "") -> str:
    """获取 PLCSIM 实例的运行状态(RUN/STOP/Off 等)"""
    target, error = _resolve_target(name)
    if error:
        return error
    result = _list_instances()
    if not result.get("success"):
        return _format_result(False, error=result.get("error") or result.get("output") or "查询失败")
    for entry in _parse_instance_lines(result.get("output", "")):
        if entry["name"] == target.plcsim_instance:
            line = f"[{entry['id']}] {entry['name']} — {entry['state']}"
            if entry["cpu"]:
                line += f" ({entry['cpu']})"
            return f"实例 `{target.plcsim_instance}` 状态:\n{line}"
    return f"实例 `{target.plcsim_instance}` 未找到或未运行"


@mcp.tool(
    name="plc_restore_from_golden",
    annotations={"destructiveHint": True},
)
async def restore_from_golden(
    name: str = "",
    golden_zip: str = "",
    storage_path: str = "",
    ip: str = "",
    auto_run: bool = False,
    confirm: bool = False,
) -> str:
    """从 golden backup 恢复 PLCSIM 实例（绕过 TIA Portal 下载）

    破坏性操作：默认只返回预览，需 confirm=True 才执行。
    底层 plcsim_api restore 命令恢复后总是自动置 RUN，无法保证
    恢复后保持 STOP，因此本工具拒绝 auto_run=False 的调用。

    Args:
        name: 实例名（默认 config.yaml 中的值）
        golden_zip: golden zip 文件路径
        storage_path: 存储目录路径
        ip: PLC 的 IP 地址
        auto_run: 恢复后是否自动置 RUN（当前实现固定为 True）
        confirm: 破坏性操作确认
    """
    target, error = _resolve_target(name, ip)
    if error:
        return error
    n = target.plcsim_instance
    gz = golden_zip or GOLDEN_ZIP
    sp = storage_path or STORAGE_PATH
    p = target.plc_ip

    if not gz or not sp:
        return "❌ 配置缺失: 请提供 golden_zip 和 storage_path 参数"
    if not os.path.exists(gz):
        return f"❌ Golden backup 文件不存在: {gz}"
    if not auto_run:
        return ("❌ 已拒绝: 底层 plcsim_api restore 命令恢复后总会自动置 RUN，"
                "无法保证恢复后保持 STOP；请显式传入 auto_run=True 并 confirm=True。")
    if not confirm:
        return _destructive_preview(
            "从 golden backup 恢复 PLCSIM 实例（恢复后自动置 RUN）",
            {"instance": n, "golden_zip": gz, "storage_path": sp, "ip": p, "auto_run": True},
        )
    result = _run_python(PLCSIM_API, ["restore", n, gz, sp, p], timeout=120)
    return _format_result(result.get("success"), error=result.get("error", "恢复失败"))


@mcp.tool(
    name="plc_archive_to_golden",
    annotations={"destructiveHint": True},
)
async def archive_to_golden(name: str = "", golden_zip: str = "", confirm: bool = False) -> str:
    """将当前 PLCSIM 实例状态保存为 golden backup

    破坏性操作：会覆盖 golden backup，默认只返回预览，需 confirm=True 才执行。
    下载到 PLCSIM 成功后调用此工具，更新 golden backup。
    下次 restore_from_golden 就能恢复到最新状态。
    """
    target, error = _resolve_target(name)
    if error:
        return error
    n = target.plcsim_instance
    gz = golden_zip or GOLDEN_ZIP
    if not gz:
        return "❌ 请提供 golden_zip 参数"
    if not confirm:
        return _destructive_preview(
            "将实例状态归档覆盖 golden backup",
            {"instance": n, "golden_zip": gz, "overwrite_existing": os.path.exists(gz)},
        )
    result = _run_python(PLCSIM_API, ["archive", n, gz], timeout=60)
    return _format_result(result.get("success"), error=result.get("error", "归档失败"))


@mcp.tool(
    name="plc_switch_to_tcpip",
    annotations={"destructiveHint": True},
)
async def switch_to_tcpip(name: str = "", ip: str = "", confirm: bool = False) -> str:
    """将 PLCSIM 实例切换到 TCP/IP 通信模式（Factory I/O 需要）

    破坏性操作：默认只返回预览，需 confirm=True 才执行。
    """
    target, error = _resolve_target(name, ip)
    if error:
        return error
    n = target.plcsim_instance
    p = target.plc_ip
    if not confirm:
        return _destructive_preview("切换 PLCSIM 实例到 TCP/IP 通信模式", {"instance": n, "ip": p})
    result = _run_python(PLCSIM_API, ["tcpip", n, p], timeout=60)
    return _format_result(result.get("success"), error=result.get("error", "切换失败"))
