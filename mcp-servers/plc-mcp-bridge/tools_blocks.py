"""PLC 块管理工具（FB/FC/OB/DB）"""
import asyncio
import os
from _helpers import mcp, _run_tiaworker, _format_result, _check_project, _handle_preview_or_dry_run, PROJECT_PATH

# ── 审计日志（强制，HMAC 链式）：与 tools_s7.py 使用同一审计链 ──
from mcp_common.audit import get_audit_logger, AuditConfigurationError, AuditStorageError

_audit = get_audit_logger()


async def _run_tiaworker_async(command: str, data: dict, timeout: int = 180) -> dict:
    """在线程池中运行 TiaWorker 子进程，避免阻塞事件循环与并发请求。"""
    return await asyncio.to_thread(_run_tiaworker, command, data, timeout=timeout)


def _audit_gate(operation: str, target: str, params: dict) -> str | None:
    """破坏性操作执行前的审计闸门（fail-closed）：审计不可用或主体未认证时拒绝执行。

    与 tools_s7.py 一致：MCP 尚无已认证会话上下文，空主体使生产控制动作被拒绝。
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


@mcp.tool(name="plc_list_blocks", annotations={"readOnlyHint": True})
async def list_blocks() -> str:
    """列出 TIA 项目中所有 PLC 块（FB/FC/OB/DB）及其编号和语言"""
    if err := _check_project(): return err
    result = await _run_tiaworker_async("list-blocks", {"ProjectPath": PROJECT_PATH}, timeout=120)
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
    result = await _run_tiaworker_async("list-dbs", {"ProjectPath": PROJECT_PATH}, timeout=120)
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
    dry_run: bool = False,
    preview: bool = False,
) -> str:
    """在 TIA 项目中创建 PLC 块

    Args:
        block_name: 块名称
        block_type: 块类型 (FB/FC/OB/DB)
        language: 编程语言 (SCL/LAD/FBD/STL)
        block_number: 块编号（0=自动分配）
        dry_run: 预览模式，不实际执行
        preview: 预览模式，返回 token 后可调用 plc_apply(token) 执行
    """
    if err := _check_project(): return err
    params = {
        "ProjectPath": PROJECT_PATH,
        "BlockName": block_name,
        "BlockType": block_type,
        "Language": language,
        "BlockNumber": block_number,
    }
    if msg := _handle_preview_or_dry_run("create-block", params, dry_run, preview):
        return msg
    if msg := _audit_gate("blocks.create_block", block_name, params):
        return msg
    result = await _run_tiaworker_async("create-block", params)
    if result.get("success"):
        data = result.get("data", {})
        warn = _audit_outcome("blocks.create_block", block_name, True,
                              f"created={data.get('blockName', block_name)} number={data.get('number', '?')}")
        return f"✅ 已创建 {block_type} `{data.get('blockName', block_name)}` (编号: {data.get('number', '?')}){warn}"
    _audit_outcome("blocks.create_block", block_name, False, result.get("error", ""))
    return _format_result(False, error=result.get("error", "创建失败"))


@mcp.tool(name="plc_export_block", annotations={"readOnlyHint": True})
async def export_block(block_name: str, output_path: str) -> str:
    """从 TIA 项目导出块为 XML 文件

    Args:
        block_name: 要导出的块名称
        output_path: 输出 XML 文件路径
    """
    if err := _check_project(): return err
    result = await _run_tiaworker_async("export-block", {
        "ProjectPath": PROJECT_PATH,
        "BlockName": block_name,
        "OutputPath": output_path,
    })
    if result.get("success"):
        return f"✅ 已导出 `{block_name}` → {output_path}"
    return _format_result(False, error=result.get("error", "导出失败"))


@mcp.tool(name="plc_import_block", annotations={"destructiveHint": True})
async def import_block(file_path: str, override: bool = False, dry_run: bool = False, preview: bool = False) -> str:
    """从 XML 文件导入块到 TIA 项目

    Args:
        file_path: XML 块文件路径
        override: 是否覆盖已存在的同名块
        dry_run: 预览模式，不实际执行
        preview: 预览模式，返回 token 后可调用 plc_apply(token) 执行
    """
    if err := _check_project(): return err
    if not os.path.exists(file_path):
        return f"❌ XML 文件不存在: {file_path}"
    params = {
        "ProjectPath": PROJECT_PATH,
        "FilePath": file_path,
        "Override": override,
    }
    if msg := _handle_preview_or_dry_run("import-block", params, dry_run, preview):
        return msg
    if msg := _audit_gate("blocks.import_block", file_path, params):
        return msg
    result = await _run_tiaworker_async("import-block", params)
    if result.get("success"):
        data = result.get("data", {})
        blocks = data.get("blocks", [])
        warn = _audit_outcome("blocks.import_block", file_path, True, f"imported={blocks}")
        return f"✅ 已导入: {', '.join(blocks)}{warn}"
    _audit_outcome("blocks.import_block", file_path, False, result.get("error", ""))
    return _format_result(False, error=result.get("error", "导入失败"))


@mcp.tool(name="plc_get_block_details", annotations={"readOnlyHint": True})
async def get_block_details(block_name: str) -> str:
    """获取指定块的详细信息（类型、编号、语言、一致性状态）

    Args:
        block_name: 块名称
    """
    if err := _check_project(): return err
    result = await _run_tiaworker_async("get-block-details", {"ProjectPath": PROJECT_PATH, "BlockName": block_name}, timeout=120)
    if result.get("success"):
        d = result.get("data", {})
        consistent = "✅" if d.get("isConsistent") else "⚠"
        return f"块 `{d.get('name')}` (#{d.get('number')})\n  类型: {d.get('type')}\n  语言: {d.get('language')}\n  一致性: {consistent}"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(name="plc_delete_block", annotations={"destructiveHint": True})
async def delete_block(block_name: str, dry_run: bool = False, preview: bool = False) -> str:
    """删除 PLC 块（FB/FC/OB/DB）

    Args:
        block_name: 要删除的块名称
        dry_run: 预览模式，不实际执行
        preview: 预览模式，返回 token 后可调用 plc_apply(token) 执行
    """
    if err := _check_project(): return err
    params = {"ProjectPath": PROJECT_PATH, "BlockName": block_name}
    if msg := _handle_preview_or_dry_run("delete-block", params, dry_run, preview):
        return msg
    if msg := _audit_gate("blocks.delete_block", block_name, params):
        return msg
    result = await _run_tiaworker_async("delete-block", params)
    if result.get("success"):
        d = result.get("data", {})
        warn = _audit_outcome("blocks.delete_block", block_name, True,
                              f"deleted={d.get('deleted')} number={d.get('number')}")
        return f"✅ 已删除 `{d.get('deleted')}` (#{d.get('number')}){warn}"
    _audit_outcome("blocks.delete_block", block_name, False, result.get("error", ""))
    return _format_result(False, error=result.get("error", "删除失败"))


@mcp.tool(name="plc_compile_block", annotations={"destructiveHint": False})
async def compile_block(block_name: str) -> str:
    """编译单个 PLC 块

    Args:
        block_name: 要编译的块名称
    """
    if err := _check_project(): return err
    result = await _run_tiaworker_async("compile-block", {"ProjectPath": PROJECT_PATH, "BlockName": block_name}, timeout=120)
    if result.get("success"):
        d = result.get("data", {})
        status = "✅ 通过" if d.get("success") else "❌ 失败"
        return f"{status} | 错误: {d.get('errors', 0)} | 警告: {d.get('warnings', 0)}"
    return _format_result(False, error=result.get("error", "编译失败"))


@mcp.tool(name="plc_create_db", annotations={"destructiveHint": False})
async def create_db(db_name: str, db_number: int = 0, dry_run: bool = False, preview: bool = False) -> str:
    """创建全局数据块 (GlobalDB)

    Args:
        db_name: 数据块名称
        db_number: 数据块编号（0=自动分配）
        dry_run: 预览模式，不实际执行
        preview: 预览模式，返回 token 后可调用 plc_apply(token) 执行
    """
    if err := _check_project(): return err
    params = {
        "ProjectPath": PROJECT_PATH,
        "DbName": db_name,
        "DbNumber": db_number,
    }
    if msg := _handle_preview_or_dry_run("create-db", params, dry_run, preview):
        return msg
    if msg := _audit_gate("blocks.create_db", db_name, params):
        return msg
    result = await _run_tiaworker_async("create-db", params)
    if result.get("success"):
        data = result.get("data", {})
        warn = _audit_outcome("blocks.create_db", db_name, True,
                              f"created={data.get('dbName', db_name)} number={data.get('number', '?')}")
        return f"✅ 已创建 DB `{data.get('dbName', db_name)}` (编号: {data.get('number', '?')}){warn}"
    _audit_outcome("blocks.create_db", db_name, False, result.get("error", ""))
    return _format_result(False, error=result.get("error", "创建失败"))


@mcp.tool(name="plc_delete_db", annotations={"destructiveHint": True})
async def delete_db(db_name: str, dry_run: bool = False, preview: bool = False) -> str:
    """删除数据块（仅限 GlobalDB/InstanceDB）

    Args:
        db_name: 要删除的数据块名称
        dry_run: 预览模式，不实际执行
        preview: 预览模式，返回 token 后可调用 plc_apply(token) 执行
    """
    if err := _check_project(): return err
    params = {"ProjectPath": PROJECT_PATH, "BlockName": db_name}
    if msg := _handle_preview_or_dry_run("delete-db", params, dry_run, preview):
        return msg
    if msg := _audit_gate("blocks.delete_db", db_name, params):
        return msg
    result = await _run_tiaworker_async("delete-db", params)
    if result.get("success"):
        d = result.get("data", {})
        warn = _audit_outcome("blocks.delete_db", db_name, True,
                              f"deleted={d.get('deleted')} number={d.get('number')}")
        return f"✅ 已删除 DB `{d.get('deleted')}` (#{d.get('number')}){warn}"
    _audit_outcome("blocks.delete_db", db_name, False, result.get("error", ""))
    return _format_result(False, error=result.get("error", "删除失败"))


@mcp.tool(name="plc_get_block_interface", annotations={"readOnlyHint": True})
async def get_block_interface(block_name: str) -> str:
    """读取 PLC 块的接口定义（Input/Output/Static/Temp 各部分的变量）

    Args:
        block_name: 块名称（如 Main, MotorControl 等）
    """
    if err := _check_project(): return err
    result = await _run_tiaworker_async("get-block-interface", {
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
