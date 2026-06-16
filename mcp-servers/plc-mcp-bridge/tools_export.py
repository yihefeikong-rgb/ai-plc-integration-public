"""CSV/XLSX 导出工具"""
import os
from _helpers import mcp, _run_tiaworker, _format_result, _check_project, _dry_run_msg, PROJECT_PATH


@mcp.tool(name="plc_export_tags_csv", annotations={"readOnlyHint": True})
async def export_tags_csv(output_path: str = "", dry_run: bool = False) -> str:
    """导出标签表为 CSV 文件

    Args:
        output_path: 输出 CSV 文件路径（默认自动生成）
        dry_run: 预览模式，不实际执行
    """
    if err := _check_project(): return err
    out = output_path or os.path.join(os.path.dirname(PROJECT_PATH), "tag_export.csv")
    params = {"ProjectPath": PROJECT_PATH, "OutputPath": out}
    if dry_run:
        return _dry_run_msg("export-tags-csv", params)
    result = _run_tiaworker("export-tags-csv", params, timeout=120)
    if result.get("success"):
        data = result.get("data", {})
        return f"✅ 已导出 {data.get('count', 0)} 个标签 → {data.get('file', out)}"
    return _format_result(False, error=result.get("error", "导出失败"))
