"""PLC 块管理工具（FB/FC/OB/DB）"""
import os
from _helpers import mcp, _run_tiaworker, _format_result, _check_project, PROJECT_PATH


@mcp.tool(name="plc_list_blocks", annotations={"readOnlyHint": True})
async def list_blocks() -> str:
    """列出 TIA 项目中所有 PLC 块（FB/FC/OB/DB）及其编号和语言"""
    if err := _check_project(): return err
    result = _run_tiaworker("list-blocks", {"ProjectPath": PROJECT_PATH}, timeout=120)
    if result.get("success"):
        data = result.get("data", {})
        blocks = data.get("blocks", [])
        if blocks:
            lines = [f"  {b['type']:10s} {b['number']:>5d}  {b['name']:<30s} {b['language']}" for b in blocks]
            return f"PLC 块 ({data.get('count', len(blocks))}):\n" + "\n".join(lines)
        return "项目中无 PLC 块"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(name="plc_list_dbs", annotations={"readOnlyHint": True})
async def list_dbs() -> str:
    """列出 TIA 项目中所有数据块（GlobalDB/InstanceDB）"""
    if err := _check_project(): return err
    result = _run_tiaworker("list-dbs", {"ProjectPath": PROJECT_PATH}, timeout=120)
    if result.get("success"):
        data = result.get("data", {})
        dbs = data.get("dbs", [])
        if dbs:
            lines = [f"  DB{d['number']:<5d} {d['name']:<30s} ({d['type']})" for d in dbs]
            return f"数据块 ({data.get('count', len(dbs))}):\n" + "\n".join(lines)
        return "项目中无数据块"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(name="plc_create_block", annotations={"destructiveHint": False})
async def create_block(
    block_name: str,
    block_type: str = "FB",
    language: str = "SCL",
    block_number: int = 0,
) -> str:
    """在 TIA 项目中创建 PLC 块

    Args:
        block_name: 块名称
        block_type: 块类型 (FB/FC/OB/DB)
        language: 编程语言 (SCL/LAD/FBD/STL)
        block_number: 块编号（0=自动分配）
    """
    if err := _check_project(): return err
    result = _run_tiaworker("create-block", {
        "ProjectPath": PROJECT_PATH,
        "BlockName": block_name,
        "BlockType": block_type,
        "Language": language,
        "BlockNumber": block_number,
    })
    if result.get("success"):
        data = result.get("data", {})
        return f"✅ 已创建 {block_type} `{data.get('blockName', block_name)}` (编号: {data.get('number', '?')})"
    return _format_result(False, error=result.get("error", "创建失败"))


@mcp.tool(name="plc_export_block", annotations={"readOnlyHint": True})
async def export_block(block_name: str, output_path: str) -> str:
    """从 TIA 项目导出块为 XML 文件

    Args:
        block_name: 要导出的块名称
        output_path: 输出 XML 文件路径
    """
    if err := _check_project(): return err
    result = _run_tiaworker("export-block", {
        "ProjectPath": PROJECT_PATH,
        "BlockName": block_name,
        "OutputPath": output_path,
    })
    if result.get("success"):
        return f"✅ 已导出 `{block_name}` → {output_path}"
    return _format_result(False, error=result.get("error", "导出失败"))


@mcp.tool(name="plc_import_block", annotations={"destructiveHint": True})
async def import_block(file_path: str, override: bool = False) -> str:
    """从 XML 文件导入块到 TIA 项目

    Args:
        file_path: XML 块文件路径
        override: 是否覆盖已存在的同名块
    """
    if err := _check_project(): return err
    if not os.path.exists(file_path):
        return f"❌ XML 文件不存在: {file_path}"
    result = _run_tiaworker("import-block", {
        "ProjectPath": PROJECT_PATH,
        "FilePath": file_path,
        "Override": override,
    })
    if result.get("success"):
        data = result.get("data", {})
        blocks = data.get("blocks", [])
        return f"✅ 已导入: {', '.join(blocks)}"
    return _format_result(False, error=result.get("error", "导入失败"))


@mcp.tool(name="plc_get_block_details", annotations={"readOnlyHint": True})
async def get_block_details(block_name: str) -> str:
    """获取指定块的详细信息（类型、编号、语言、一致性状态）

    Args:
        block_name: 块名称
    """
    if err := _check_project(): return err
    result = _run_tiaworker("get-block-details", {"ProjectPath": PROJECT_PATH, "BlockName": block_name}, timeout=120)
    if result.get("success"):
        d = result.get("data", {})
        consistent = "✅" if d.get("isConsistent") else "⚠"
        return f"块 `{d.get('name')}` (#{d.get('number')})\n  类型: {d.get('type')}\n  语言: {d.get('language')}\n  一致性: {consistent}"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(name="plc_delete_block", annotations={"destructiveHint": True})
async def delete_block(block_name: str) -> str:
    """删除 PLC 块（FB/FC/OB/DB）

    Args:
        block_name: 要删除的块名称
    """
    if err := _check_project(): return err
    result = _run_tiaworker("delete-block", {"ProjectPath": PROJECT_PATH, "BlockName": block_name})
    if result.get("success"):
        d = result.get("data", {})
        return f"✅ 已删除 `{d.get('deleted')}` (#{d.get('number')})"
    return _format_result(False, error=result.get("error", "删除失败"))


@mcp.tool(name="plc_compile_block", annotations={"destructiveHint": False})
async def compile_block(block_name: str) -> str:
    """编译单个 PLC 块

    Args:
        block_name: 要编译的块名称
    """
    if err := _check_project(): return err
    result = _run_tiaworker("compile-block", {"ProjectPath": PROJECT_PATH, "BlockName": block_name}, timeout=120)
    if result.get("success"):
        d = result.get("data", {})
        status = "✅ 通过" if d.get("success") else "❌ 失败"
        return f"{status} | 错误: {d.get('errors', 0)} | 警告: {d.get('warnings', 0)}"
    return _format_result(False, error=result.get("error", "编译失败"))


@mcp.tool(name="plc_create_db", annotations={"destructiveHint": False})
async def create_db(db_name: str, db_number: int = 0) -> str:
    """创建全局数据块 (GlobalDB)

    Args:
        db_name: 数据块名称
        db_number: 数据块编号（0=自动分配）
    """
    if err := _check_project(): return err
    result = _run_tiaworker("create-db", {
        "ProjectPath": PROJECT_PATH,
        "DbName": db_name,
        "DbNumber": db_number,
    })
    if result.get("success"):
        data = result.get("data", {})
        return f"✅ 已创建 DB `{data.get('dbName', db_name)}` (编号: {data.get('number', '?')})"
    return _format_result(False, error=result.get("error", "创建失败"))


@mcp.tool(name="plc_delete_db", annotations={"destructiveHint": True})
async def delete_db(db_name: str) -> str:
    """删除数据块（仅限 GlobalDB/InstanceDB）

    Args:
        db_name: 要删除的数据块名称
    """
    if err := _check_project(): return err
    result = _run_tiaworker("delete-db", {"ProjectPath": PROJECT_PATH, "BlockName": db_name})
    if result.get("success"):
        d = result.get("data", {})
        return f"✅ 已删除 DB `{d.get('deleted')}` (#{d.get('number')})"
    return _format_result(False, error=result.get("error", "删除失败"))


@mcp.tool(name="plc_get_block_interface", annotations={"readOnlyHint": True})
async def get_block_interface(block_name: str) -> str:
    """读取 PLC 块的接口定义（Input/Output/Static/Temp 各部分的变量）

    Args:
        block_name: 块名称（如 Main, MotorControl 等）
    """
    if err := _check_project(): return err
    result = _run_tiaworker("get-block-interface", {
        "ProjectPath": PROJECT_PATH,
        "BlockName": block_name,
    }, timeout=120)
    if result.get("success"):
        data = result.get("data", {})
        sections = data.get("sections", [])
        if sections:
            lines = [f"块 `{data.get('blockName', block_name)}` 接口:"]
            for s in sections:
                lines.append(f"\n  [{s['section']}]")
                for m in s.get("members", []):
                    lines.append(f"    {m['name']} : {m['dataType']}")
            return "\n".join(lines)
        return f"块 `{block_name}` 无接口定义"
    return _format_result(False, error=result.get("error", "读取失败"))
