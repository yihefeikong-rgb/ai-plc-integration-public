"""UDT 和 Watch 表管理工具"""
from _helpers import mcp, _run_tiaworker, _format_result, _check_project, _dry_run_msg, _handle_preview_or_dry_run, PROJECT_PATH

# ── 审计日志（强制，HMAC 链式）：与 tools_blocks.py / tools_s7.py 同一审计链 ──
from mcp_common.audit import get_audit_logger, AuditConfigurationError, AuditStorageError

_audit = get_audit_logger()


def _audit_gate(operation: str, target: str, params: dict) -> str | None:
    """破坏性操作执行前的审计闸门（fail-closed）：审计不可用或主体未认证时拒绝执行。"""
    try:
        _audit.begin_control_operation(operation, target, "", params)
    except (AuditConfigurationError, AuditStorageError) as exc:
        return f"🚫 操作被拒绝: {exc}"
    return None


def _audit_outcome(operation: str, target: str, success: bool, detail: str, operator: str = "") -> str:
    """记录破坏性操作结果审计；写入失败返回告警后缀，不掩盖已发生的副作用。"""
    try:
        _audit.log(operation, target, "", operator=operator, success=success, detail=detail)
    except Exception as exc:
        return f" ⚠️(审计写入失败: {exc})"
    return ""


# ── UDT 管理 ──

@mcp.tool(name="plc_list_udts", annotations={"readOnlyHint": True})
async def list_udts() -> str:
    """列出 TIA 项目中所有用户自定义类型（UDT）"""
    if err := _check_project(): return err
    result = _run_tiaworker("list-udts", {"ProjectPath": PROJECT_PATH}, timeout=120)
    if result.get("success"):
        data = result.get("data", {})
        udts = data.get("udts", [])
        if udts:
            lines = [f"- {u['name']}" for u in udts]
            return f"UDT 列表 ({data.get('count', len(udts))}):\n" + "\n".join(lines)
        return "项目中无 UDT"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(name="plc_create_udt", annotations={"destructiveHint": False})
async def create_udt(udt_name: str, dry_run: bool = False, preview: bool = False) -> str:
    """创建空的用户自定义类型（UDT）

    Args:
        udt_name: UDT 名称
        dry_run: 预览模式，不实际执行
        preview: 预览模式，返回 token 后可调用 plc_apply(token) 执行
    """
    if err := _check_project(): return err
    params = {"ProjectPath": PROJECT_PATH, "UdtName": udt_name}
    if msg := _handle_preview_or_dry_run("create-udt", params, dry_run, preview):
        return msg
    if msg := _audit_gate("types.create_udt", udt_name, params):
        return msg
    result = _run_tiaworker("create-udt", params)
    if result.get("success"):
        warn = _audit_outcome("types.create_udt", udt_name, True, f"udt={udt_name}")
        return f"✅ 已创建 UDT `{udt_name}`{warn}"
    _audit_outcome("types.create_udt", udt_name, False, result.get("error", "创建失败"))
    return _format_result(False, error=result.get("error", "创建失败"))


@mcp.tool(name="plc_delete_udt", annotations={"destructiveHint": True})
async def delete_udt(udt_name: str, dry_run: bool = False, preview: bool = False) -> str:
    """删除用户自定义类型（UDT）

    Args:
        udt_name: 要删除的 UDT 名称
        dry_run: 预览模式，不实际执行
        preview: 预览模式，返回 token 后可调用 plc_apply(token) 执行
    """
    if err := _check_project(): return err
    params = {"ProjectPath": PROJECT_PATH, "UdtName": udt_name}
    if msg := _handle_preview_or_dry_run("delete-udt", params, dry_run, preview):
        return msg
    if msg := _audit_gate("types.delete_udt", udt_name, params):
        return msg
    result = _run_tiaworker("delete-udt", params)
    if result.get("success"):
        warn = _audit_outcome("types.delete_udt", udt_name, True, f"udt={udt_name}")
        return f"✅ 已删除 UDT `{udt_name}`{warn}"
    _audit_outcome("types.delete_udt", udt_name, False, result.get("error", "删除失败"))
    return _format_result(False, error=result.get("error", "删除失败"))


# ── Watch 表管理 ──

@mcp.tool(name="plc_list_watch_tables", annotations={"readOnlyHint": True})
async def list_watch_tables() -> str:
    """列出 TIA 项目中所有监控表（Watch Table）"""
    if err := _check_project(): return err
    result = _run_tiaworker("list-watch-tables", {"ProjectPath": PROJECT_PATH}, timeout=120)
    if result.get("success"):
        data = result.get("data", {})
        tables = data.get("watchTables", [])
        if tables:
            lines = [f"- {t['name']}" for t in tables]
            return f"监控表 ({data.get('count', len(tables))}):\n" + "\n".join(lines)
        return "项目中无监控表"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(name="plc_create_watch_table", annotations={"destructiveHint": False})
async def create_watch_table(watch_table_name: str, dry_run: bool = False) -> str:
    """创建新的监控表（Watch Table）

    Args:
        watch_table_name: 监控表名称
        dry_run: 预览模式，不实际执行
    """
    if err := _check_project(): return err
    params = {"ProjectPath": PROJECT_PATH, "WatchTableName": watch_table_name}
    if dry_run:
        return _dry_run_msg("create-watch-table", params)
    if msg := _audit_gate("types.create_watch_table", watch_table_name, params):
        return msg
    result = _run_tiaworker("create-watch-table", params)
    if result.get("success"):
        warn = _audit_outcome("types.create_watch_table", watch_table_name, True, f"watch_table={watch_table_name}")
        return f"✅ 已创建监控表 `{watch_table_name}`{warn}"
    _audit_outcome("types.create_watch_table", watch_table_name, False, result.get("error", "创建失败"))
    return _format_result(False, error=result.get("error", "创建失败"))


@mcp.tool(name="plc_delete_watch_table", annotations={"destructiveHint": True})
async def delete_watch_table(watch_table_name: str, dry_run: bool = False) -> str:
    """删除监控表（Watch Table）

    Args:
        watch_table_name: 要删除的监控表名称
        dry_run: 预览模式，不实际执行
    """
    if err := _check_project(): return err
    params = {"ProjectPath": PROJECT_PATH, "WatchTableName": watch_table_name}
    if dry_run:
        return _dry_run_msg("delete-watch-table", params)
    if msg := _audit_gate("types.delete_watch_table", watch_table_name, params):
        return msg
    result = _run_tiaworker("delete-watch-table", params)
    if result.get("success"):
        warn = _audit_outcome("types.delete_watch_table", watch_table_name, True, f"watch_table={watch_table_name}")
        return f"✅ 已删除监控表 `{watch_table_name}`{warn}"
    _audit_outcome("types.delete_watch_table", watch_table_name, False, result.get("error", "删除失败"))
    return _format_result(False, error=result.get("error", "删除失败"))
