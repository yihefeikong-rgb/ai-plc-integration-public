"""UDT 和 Watch 表管理工具"""
import json
from _helpers import mcp, _run_tiaworker, _format_result, _check_project, _dry_run_msg, _preview_action, PROJECT_PATH


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
    if dry_run:
        return _dry_run_msg("create-udt", params)
    if preview:
        r = _preview_action("create-udt", params)
        return f"🔍 预览:\n```json\n{json.dumps(r['preview'], ensure_ascii=False, indent=2)}\n```\nToken: `{r['token']}`\n使用 `plc_apply(token=\"{r['token']}\")` 执行"
    result = _run_tiaworker("create-udt", params)
    if result.get("success"):
        return f"✅ 已创建 UDT `{udt_name}`"
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
    if dry_run:
        return _dry_run_msg("delete-udt", params)
    if preview:
        r = _preview_action("delete-udt", params)
        return f"🔍 预览:\n```json\n{json.dumps(r['preview'], ensure_ascii=False, indent=2)}\n```\nToken: `{r['token']}`\n使用 `plc_apply(token=\"{r['token']}\")` 执行"
    result = _run_tiaworker("delete-udt", params)
    if result.get("success"):
        return f"✅ 已删除 UDT `{udt_name}`"
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
    result = _run_tiaworker("create-watch-table", params)
    if result.get("success"):
        return f"✅ 已创建监控表 `{watch_table_name}`"
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
    result = _run_tiaworker("delete-watch-table", params)
    if result.get("success"):
        return f"✅ 已删除监控表 `{watch_table_name}`"
    return _format_result(False, error=result.get("error", "删除失败"))
