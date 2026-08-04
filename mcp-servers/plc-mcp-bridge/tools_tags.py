"""标签表管理工具"""
import asyncio
from _helpers import mcp, _run_tiaworker, _format_result, _check_project, _dry_run_msg, _handle_preview_or_dry_run, PROJECT_PATH

# ── 审计日志（强制，HMAC 链式）：与 tools_blocks.py 使用同一审计链 ──
from mcp_common.audit import get_audit_logger, AuditConfigurationError, AuditStorageError

_audit = get_audit_logger()


async def _run_tiaworker_async(command: str, data: dict, timeout: int = 180) -> dict:
    """在线程池中运行 TiaWorker 子进程，避免阻塞事件循环与并发请求。"""
    return await asyncio.to_thread(_run_tiaworker, command, data, timeout=timeout)


def _audit_gate(operation: str, target: str, params: dict) -> str | None:
    """破坏性操作执行前的审计闸门（fail-closed）：审计不可用或主体未认证时拒绝执行。

    与 tools_blocks.py 一致：MCP 尚无已认证会话上下文，空主体使生产控制动作被拒绝。
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


@mcp.tool(name="plc_list_tag_tables", annotations={"readOnlyHint": True})
async def list_tag_tables() -> str:
    """列出 TIA 项目中所有标签表及标签数量"""
    if err := _check_project(): return err
    result = await _run_tiaworker_async("list-tags", {"ProjectPath": PROJECT_PATH})
    if result.get("success"):
        data = result.get("data", {})
        tables = data.get("tables", [])
        if tables:
            lines = [f"- {t['name']} ({t['tagCount']} 个标签)" for t in tables]
            return "标签表:\n" + "\n".join(lines)
        return "项目中无标签表"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(name="plc_get_tags", annotations={"readOnlyHint": True})
async def get_tags(tag_table_name: str) -> str:
    """获取指定标签表中的所有标签

    Args:
        tag_table_name: 标签表名称
    """
    if err := _check_project(): return err
    result = await _run_tiaworker_async("get-tags", {
        "ProjectPath": PROJECT_PATH,
        "TagTableName": tag_table_name,
    })
    if result.get("success"):
        data = result.get("data", {})
        tags = data.get("tags", [])
        if tags:
            lines = [f"- {t['name']} : {t['dataType']} @ {t['address']}" for t in tags]
            return f"标签表 `{tag_table_name}` ({len(tags)} 个标签):\n" + "\n".join(lines)
        return f"标签表 `{tag_table_name}` 为空"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(name="plc_add_tag", annotations={"destructiveHint": False})
async def add_tag(
    tag_table_name: str,
    tag_name: str,
    data_type: str,
    logical_address: str = "",
    dry_run: bool = False,
    preview: bool = False,
) -> str:
    """向标签表添加标签

    Args:
        tag_table_name: 标签表名称
        tag_name: 标签名称
        data_type: 数据类型 (Bool/Int/Real/Word 等)
        logical_address: 逻辑地址 (如 %M0.0, %MW100)
        dry_run: 预览模式，不实际执行
        preview: 预览模式，返回 token 后可调用 plc_apply(token) 执行
    """
    if err := _check_project(): return err
    params = {
        "ProjectPath": PROJECT_PATH,
        "TagTableName": tag_table_name,
        "TagName": tag_name,
        "DataType": data_type,
        "LogicalAddress": logical_address,
    }
    if msg := _handle_preview_or_dry_run("add-tag", params, dry_run, preview):
        return msg
    if msg := _audit_gate("tags.add_tag", tag_name, params):
        return msg
    result = await _run_tiaworker_async("add-tag", params)
    if result.get("success"):
        data = result.get("data", {})
        warn = _audit_outcome("tags.add_tag", tag_name, True,
                              f"table={tag_table_name} address={data.get('address', logical_address)}")
        return f"✅ 已添加标签 `{data.get('tagName', tag_name)}` : {data.get('dataType', data_type)} @ {data.get('address', logical_address)}{warn}"
    _audit_outcome("tags.add_tag", tag_name, False, result.get("error", ""))
    return _format_result(False, error=result.get("error", "添加失败"))


@mcp.tool(name="plc_create_tag_table", annotations={"destructiveHint": False})
async def create_tag_table(tag_table_name: str, dry_run: bool = False) -> str:
    """创建新的标签表

    Args:
        tag_table_name: 标签表名称
        dry_run: 预览模式，不实际执行
    """
    if err := _check_project(): return err
    params = {"ProjectPath": PROJECT_PATH, "TagTableName": tag_table_name}
    if dry_run:
        return _dry_run_msg("create-tag-table", params)
    if msg := _audit_gate("tags.create_tag_table", tag_table_name, params):
        return msg
    result = await _run_tiaworker_async("create-tag-table", params)
    if result.get("success"):
        warn = _audit_outcome("tags.create_tag_table", tag_table_name, True,
                              f"created={result.get('data', {}).get('tableName', tag_table_name)}")
        return f"✅ 已创建标签表 `{result.get('data', {}).get('tableName', tag_table_name)}`{warn}"
    _audit_outcome("tags.create_tag_table", tag_table_name, False, result.get("error", ""))
    return _format_result(False, error=result.get("error", "创建失败"))


@mcp.tool(name="plc_delete_tag_table", annotations={"destructiveHint": True})
async def delete_tag_table(tag_table_name: str, dry_run: bool = False) -> str:
    """删除标签表

    Args:
        tag_table_name: 要删除的标签表名称
        dry_run: 预览模式，不实际执行
    """
    if err := _check_project(): return err
    params = {"ProjectPath": PROJECT_PATH, "TagTableName": tag_table_name}
    if dry_run:
        return _dry_run_msg("delete-tag-table", params)
    if msg := _audit_gate("tags.delete_tag_table", tag_table_name, params):
        return msg
    result = await _run_tiaworker_async("delete-tag-table", params)
    if result.get("success"):
        warn = _audit_outcome("tags.delete_tag_table", tag_table_name, True, "deleted")
        return f"✅ 已删除标签表 `{tag_table_name}`{warn}"
    _audit_outcome("tags.delete_tag_table", tag_table_name, False, result.get("error", ""))
    return _format_result(False, error=result.get("error", "删除失败"))


@mcp.tool(name="plc_search_tags", annotations={"readOnlyHint": True})
async def search_tags(query: str) -> str:
    """跨所有标签表搜索标签（按名称模糊匹配）

    Args:
        query: 搜索关键词
    """
    if err := _check_project(): return err
    result = await _run_tiaworker_async("search-tag", {
        "ProjectPath": PROJECT_PATH,
        "Query": query,
    })
    if result.get("success"):
        data = result.get("data", {})
        results = data.get("results", [])
        if results:
            lines = [f"  [{r['table']}] {r['name']} : {r['dataType']} @ {r['address']}" for r in results]
            return f"搜索 '{data.get('query', query)}' ({len(results)} 个结果):\n" + "\n".join(lines)
        return f"未找到匹配 '{query}' 的标签"
    return _format_result(False, error=result.get("error", "搜索失败"))


@mcp.tool(name="plc_check_tag_conflicts", annotations={"readOnlyHint": True})
async def check_tag_conflicts() -> str:
    """检测所有标签表中是否存在逻辑地址冲突（同一地址被多个标签占用）"""
    if err := _check_project(): return err
    result = await _run_tiaworker_async("check-tag-conflicts", {"ProjectPath": PROJECT_PATH}, timeout=120)
    if result.get("success"):
        d = result.get("data", {})
        conflicts = d.get("conflicts", [])
        if conflicts:
            lines = [f"⚠ 发现 {d.get('totalConflicts', len(conflicts))} 个地址冲突："]
            for c in conflicts:
                lines.append(f"\n  地址 {c['address']}:")
                for tag in c.get("tags", []):
                    lines.append(f"    - {tag}")
            return "\n".join(lines)
        return "✅ 无标签地址冲突"
    return _format_result(False, error=result.get("error", "检测失败"))


@mcp.tool(name="plc_find_free_address", annotations={"readOnlyHint": True})
async def find_free_address(area: str = "M", start_byte: int = 0) -> str:
    """查找指定区域内下一个空闲的地址

    Args:
        area: 区域 (M/I/Q)
        start_byte: 起始字节偏移
    """
    if err := _check_project(): return err
    result = await _run_tiaworker_async("find-free-address", {
        "ProjectPath": PROJECT_PATH,
        "Area": area,
        "StartByte": start_byte,
    })
    if result.get("success"):
        d = result.get("data", {})
        return f"区域 {d.get('area', area)} 中下一个空闲地址: {d.get('address', '?')} (字节 {d.get('freeByte', '?')})"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(name="plc_delete_tag", annotations={"destructiveHint": True})
async def delete_tag(tag_table_name: str, tag_name: str, dry_run: bool = False, preview: bool = False) -> str:
    """从标签表中删除标签

    Args:
        tag_table_name: 标签表名称
        tag_name: 要删除的标签名称
        dry_run: 预览模式，不实际执行
        preview: 预览模式，返回 token 后可调用 plc_apply(token) 执行
    """
    if err := _check_project(): return err
    params = {
        "ProjectPath": PROJECT_PATH,
        "TagTableName": tag_table_name,
        "TagName": tag_name,
    }
    if msg := _handle_preview_or_dry_run("delete-tag", params, dry_run, preview):
        return msg
    if msg := _audit_gate("tags.delete_tag", tag_name, params):
        return msg
    result = await _run_tiaworker_async("delete-tag", params)
    if result.get("success"):
        warn = _audit_outcome("tags.delete_tag", tag_name, True, f"table={tag_table_name}")
        return f"✅ 已删除标签 `{tag_name}`{warn}"
    _audit_outcome("tags.delete_tag", tag_name, False, result.get("error", ""))
    return _format_result(False, error=result.get("error", "删除失败"))
