"""标签表管理工具"""
import json
from _helpers import mcp, _run_tiaworker, _format_result, _check_project, _dry_run_msg, _preview_action, PROJECT_PATH


@mcp.tool(name="plc_list_tag_tables", annotations={"readOnlyHint": True})
async def list_tag_tables() -> str:
    """列出 TIA 项目中所有标签表及标签数量"""
    if err := _check_project(): return err
    result = _run_tiaworker("list-tags", {"ProjectPath": PROJECT_PATH})
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
    result = _run_tiaworker("get-tags", {
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
    if dry_run:
        return _dry_run_msg("add-tag", params)
    if preview:
        r = _preview_action("add-tag", params)
        return f"🔍 预览:\n```json\n{json.dumps(r['preview'], ensure_ascii=False, indent=2)}\n```\nToken: `{r['token']}`\n使用 `plc_apply(token=\"{r['token']}\")` 执行"
    result = _run_tiaworker("add-tag", params)
    if result.get("success"):
        data = result.get("data", {})
        return f"✅ 已添加标签 `{data.get('tagName', tag_name)}` : {data.get('dataType', data_type)} @ {data.get('address', logical_address)}"
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
    result = _run_tiaworker("create-tag-table", params)
    if result.get("success"):
        return f"✅ 已创建标签表 `{result.get('data', {}).get('tableName', tag_table_name)}`"
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
    result = _run_tiaworker("delete-tag-table", params)
    if result.get("success"):
        return f"✅ 已删除标签表 `{tag_table_name}`"
    return _format_result(False, error=result.get("error", "删除失败"))


@mcp.tool(name="plc_search_tags", annotations={"readOnlyHint": True})
async def search_tags(query: str) -> str:
    """跨所有标签表搜索标签（按名称模糊匹配）

    Args:
        query: 搜索关键词
    """
    if err := _check_project(): return err
    result = _run_tiaworker("search-tag", {
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
    result = _run_tiaworker("check-tag-conflicts", {"ProjectPath": PROJECT_PATH}, timeout=120)
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
    result = _run_tiaworker("find-free-address", {
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
    if dry_run:
        return _dry_run_msg("delete-tag", params)
    if preview:
        r = _preview_action("delete-tag", params)
        return f"🔍 预览:\n```json\n{json.dumps(r['preview'], ensure_ascii=False, indent=2)}\n```\nToken: `{r['token']}`\n使用 `plc_apply(token=\"{r['token']}\")` 执行"
    result = _run_tiaworker("delete-tag", params)
    if result.get("success"):
        return f"✅ 已删除标签 `{tag_name}`"
    return _format_result(False, error=result.get("error", "删除失败"))
