"""项目管理、硬件信息、交叉引用、编译诊断工具"""
import os
from _helpers import mcp, _run_tiaworker, _format_result, _check_project, _dry_run_msg, PROJECT_PATH


# ── 项目基础 ──

@mcp.tool(name="plc_compile_project", annotations={"destructiveHint": False})
async def compile_project() -> str:
    """编译 TIA Portal 项目（通过 TiaWorker.exe）

    前置条件:
      1. TIA Portal V21 已安装
      2. 项目路径已配置在 config.yaml 中
    """
    if err := _check_project(): return err
    result = _run_tiaworker("compile", {"ProjectPath": PROJECT_PATH})
    if result.get("success"):
        data = result.get("data", {})
        return _format_result(True, data={
            "project": os.path.basename(PROJECT_PATH),
            "errors": data.get("errors", 0),
            "warnings": data.get("warnings", 0),
        })
    return _format_result(False, error=result.get("error", "编译失败"))


@mcp.tool(name="plc_list_devices", annotations={"readOnlyHint": True})
async def list_devices() -> str:
    """列出 TIA Portal 项目中的 PLC 设备"""
    if err := _check_project(): return err
    result = _run_tiaworker("list-devices", {"ProjectPath": PROJECT_PATH})
    if result.get("success"):
        data = result.get("data", {})
        devices = data.get("devices", [])
        if devices:
            lines = [f"- {d['name']} ({d['type']})" for d in devices]
            return f"TIA 项目设备:\n" + "\n".join(lines)
        return "项目中未找到设备"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(name="plc_save_project", annotations={"destructiveHint": False})
async def save_project() -> str:
    """保存 TIA Portal 项目"""
    if err := _check_project(): return err
    result = _run_tiaworker("save-project", {"ProjectPath": PROJECT_PATH})
    if result.get("success"):
        return f"✅ 项目已保存: {result.get('data', {}).get('saved', '')}"
    return _format_result(False, error=result.get("error", "保存失败"))


@mcp.tool(name="plc_get_project_info", annotations={"readOnlyHint": True})
async def get_project_info() -> str:
    """获取当前 TIA 项目的名称、路径和设备数量"""
    if err := _check_project(): return err
    result = _run_tiaworker("get-project-info", {"ProjectPath": PROJECT_PATH})
    if result.get("success"):
        d = result.get("data", {})
        return f"项目: {d.get('name', '?')}\n路径: {d.get('path', '?')}\n设备数: {d.get('deviceCount', '?')}"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(name="plc_create_project", annotations={"destructiveHint": False})
async def create_project(project_name: str, parent_directory: str = "", dry_run: bool = False) -> str:
    """创建新的 TIA Portal 项目

    Args:
        project_name: 项目名称
        parent_directory: 父目录路径（默认使用项目文件所在目录）
        dry_run: 预览模式，不实际执行
    """
    parent = parent_directory or os.path.dirname(PROJECT_PATH)
    if not os.path.isdir(parent):
        return f"❌ 目录不存在: {parent}"
    params = {"ProjectName": project_name, "ParentDirectory": parent}
    if dry_run:
        return _dry_run_msg("create-project", params)
    result = _run_tiaworker("create-project", params, timeout=180)
    if result.get("success"):
        d = result.get("data", {})
        return f"✅ 项目已创建: {d.get('name')} → {d.get('path')}"
    return _format_result(False, error=result.get("error", "创建失败"))


@mcp.tool(name="plc_archive_project", annotations={"destructiveHint": False})
async def archive_project(output_dir: str = "", archive_name: str = "", dry_run: bool = False) -> str:
    """将当前 TIA 项目归档为 .zap 文件

    Args:
        output_dir: 输出目录（默认项目同级目录）
        archive_name: 归档文件名（默认项目名）
        dry_run: 预览模式，不实际执行
    """
    if err := _check_project(): return err
    out = output_dir or os.path.dirname(PROJECT_PATH)
    params = {"ProjectPath": PROJECT_PATH, "OutputDir": out, "ArchiveName": archive_name or None}
    if dry_run:
        return _dry_run_msg("archive-project", params)
    result = _run_tiaworker("archive-project", params, timeout=180)
    if result.get("success"):
        d = result.get("data", {})
        return f"✅ 已归档: {d.get('archiveName')} → {d.get('outputDir')}"
    return _format_result(False, error=result.get("error", "归档失败"))


@mcp.tool(name="plc_close_project", annotations={"destructiveHint": True})
async def close_project(save: bool = True, dry_run: bool = False) -> str:
    """关闭当前 TIA Portal 项目

    Args:
        save: 关闭前是否保存（默认 True）
        dry_run: 预览模式，不实际执行
    """
    if err := _check_project(): return err
    params = {"ProjectPath": PROJECT_PATH, "Save": save}
    if dry_run:
        return _dry_run_msg("close-project", params)
    result = _run_tiaworker("close-project", params)
    if result.get("success"):
        d = result.get("data", {})
        return f"✅ 项目已关闭" + (" (已保存)" if d.get("saved") else "")
    return _format_result(False, error=result.get("error", "关闭失败"))


@mcp.tool(name="plc_list_backups", annotations={"readOnlyHint": True})
async def list_backups() -> str:
    """列出项目的自动备份列表"""
    if err := _check_project(): return err
    result = _run_tiaworker("list-backups", {"ProjectPath": PROJECT_PATH})
    if result.get("success"):
        d = result.get("data", {})
        backups = d.get("backups", [])
        if backups:
            lines = [f"备份 ({d.get('count', len(backups))} 份):"]
            for b in backups:
                lines.append(f"  [{b.get('created', '?')}] {b.get('name', '?')}")
            return "\n".join(lines)
        return "暂无备份"
    return _format_result(False, error=result.get("error", "查询失败"))


# ── 硬件信息 ──

@mcp.tool(name="plc_get_hardware_info", annotations={"readOnlyHint": True})
async def get_hardware_info() -> str:
    """获取 TIA 项目中所有设备的硬件配置（机架/插槽结构）"""
    if err := _check_project(): return err
    result = _run_tiaworker("get-hardware-info", {"ProjectPath": PROJECT_PATH}, timeout=120)
    if result.get("success"):
        d = result.get("data", {})
        devices = d.get("devices", [])
        if devices:
            lines = [f"硬件配置 ({d.get('deviceCount', len(devices))} 台设备)："]
            for dev in devices:
                lines.append(f"\n  {dev['name']} ({dev['type']})")
                for item in dev.get("items", []):
                    indent = "  " * (item["depth"] + 1)
                    lines.append(f"{indent}|- {item['name']} [{item['type']}]")
            return "\n".join(lines)
        return "项目中无硬件设备"
    return _format_result(False, error=result.get("error", "查询失败"))


# ── 交叉引用分析 ──

@mcp.tool(name="plc_find_unused_blocks", annotations={"readOnlyHint": True})
async def find_unused_blocks() -> str:
    """查找项目中未被调用的 PLC 块（通过 XML 交叉引用分析）"""
    if err := _check_project(): return err
    result = _run_tiaworker("find-unused-blocks", {"ProjectPath": PROJECT_PATH}, timeout=300)
    if result.get("success"):
        d = result.get("data", {})
        unused = d.get("unusedBlocks", [])
        if unused:
            lines = [f"未被引用的块 ({len(unused)})："]
            for b in unused:
                lines.append(f"  ! {b}")
            return "\n".join(lines)
        return "✅ 所有块均有引用"
    return _format_result(False, error=result.get("error", "分析失败"))


@mcp.tool(name="plc_find_callers", annotations={"readOnlyHint": True})
async def find_callers(block_name: str) -> str:
    """查找引用/调用指定块的所有块

    Args:
        block_name: 要查询的块名称
    """
    if err := _check_project(): return err
    result = _run_tiaworker("find-callers", {
        "ProjectPath": PROJECT_PATH,
        "BlockName": block_name,
    }, timeout=300)
    if result.get("success"):
        d = result.get("data", {})
        callers = d.get("callers", [])
        if callers:
            lines = [f"引用 `{block_name}` 的块 ({len(callers)})："]
            for c in callers:
                lines.append(f"  -> {c}")
            return "\n".join(lines)
        return f"没有块引用 `{block_name}`"
    return _format_result(False, error=result.get("error", "分析失败"))


# ── 编译诊断 ──

@mcp.tool(name="plc_get_compiler_errors", annotations={"readOnlyHint": True})
async def get_compiler_errors() -> str:
    """编译项目并返回详细的错误/警告信息"""
    if err := _check_project(): return err
    result = _run_tiaworker("get-compiler-errors", {"ProjectPath": PROJECT_PATH}, timeout=180)
    if result.get("success"):
        d = result.get("data", {})
        status = "✅ 通过" if d.get("success") else "❌ 有错误"
        lines = [f"{status} | 错误: {d.get('errors', 0)} | 警告: {d.get('warnings', 0)}"]
        for msg in d.get("messages", []):
            icon = "X" if msg.get("state") == "Error" else "!"
            lines.append(f"  [{icon}] [{msg.get('path', '')}] {msg.get('description', '')}")
        return "\n".join(lines)
    return _format_result(False, error=result.get("error", "编译失败"))


@mcp.tool(name="plc_check_consistency", annotations={"readOnlyHint": True})
async def check_consistency() -> str:
    """检查所有块的一致性状态"""
    if err := _check_project(): return err
    result = _run_tiaworker("check-consistency", {"ProjectPath": PROJECT_PATH}, timeout=120)
    if result.get("success"):
        d = result.get("data", {})
        lines = [f"一致性检查: {d.get('consistent', 0)}/{d.get('total', 0)} 通过"]
        inconsistent = [b for b in d.get("blocks", []) if not b.get("isConsistent")]
        if inconsistent:
            lines.append("不一致的块:")
            for b in inconsistent:
                lines.append(f"  ! {b['name']} (#{b['number']})")
        return "\n".join(lines)
    return _format_result(False, error=result.get("error", "检查失败"))


@mcp.tool(name="plc_export_all_xml", annotations={"readOnlyHint": True})
async def export_all_xml(output_dir: str = "") -> str:
    """将所有 PLC 块导出为 XML 文件到指定目录

    Args:
        output_dir: 输出目录（默认使用配置的 output_dir）
    """
    if err := _check_project(): return err
    out = output_dir or os.path.join(os.path.dirname(PROJECT_PATH), "xml_export")
    result = _run_tiaworker("export-all-xml", {
        "ProjectPath": PROJECT_PATH,
        "OutputDir": out,
    }, timeout=300)
    if result.get("success"):
        d = result.get("data", {})
        msg = f"✅ 已导出 {d.get('exported', 0)} 个块 -> {d.get('outputDir', out)}"
        if d.get("failed", 0) > 0:
            msg += f"\n! {d['failed']} 个块导出失败: {', '.join(d.get('failedBlocks', []))}"
        return msg
    return _format_result(False, error=result.get("error", "导出失败"))
