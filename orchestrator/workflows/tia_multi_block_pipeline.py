"""
多块依赖顺序工作流：按依赖顺序导入多个 PLC 程序块。

依赖顺序:
    UDT(1) -> 变量表(2) -> 全局DB(3) -> FC/FB/OB(4) -> 实例DB(5) -> 编译(6)

输入格式:
    {
      "blocks": [
        {"type": "UDT", "name": "MotorParams", "scl_code": "TYPE \"MotorParams\"\n..."},
        {"type": "DB", "name": "DB_Process", "scl_code": "DATA_BLOCK \"DB_Process\"\n..."},
        {"type": "FB", "name": "MotorCtrl", "scl_code": "FUNCTION_BLOCK \"MotorCtrl\"\n..."}
      ]
    }
"""
from __future__ import annotations

import logging
from typing import Any

from orchestrator.core import WorkflowContext, OrchestratorEngine

_logger = logging.getLogger(__name__)

# 依赖排序权重: 数字越小越先执行
_ORDER_WEIGHT: dict[str, int] = {
    "UDT": 1,
    "TAG_TABLE": 2,
    "DB": 3,          # 全局 DB
    "FC": 4,
    "FB": 4,
    "OB": 4,
    "INSTANCE_DB": 5,
    "COMPILE": 6,
}


def _sort_blocks_by_dependency(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按依赖顺序排序块列表。

    UDT -> 变量表 -> 全局DB -> FC/FB/OB -> 实例DB
    """
    return sorted(blocks, key=lambda b: _ORDER_WEIGHT.get(b.get("type", "").upper(), 99))


def register_tia_multi_block_pipeline_workflow(engine: OrchestratorEngine) -> None:
    """向编排引擎注册 tia_multi_block_pipeline 工作流"""

    @engine.workflow("tia_multi_block_pipeline")
    async def tia_multi_block_pipeline(ctx: WorkflowContext) -> dict[str, Any]:
        """按依赖顺序导入多个 PLC 程序块。

        从 ctx.input 读取参数:
            blocks: 块列表，每个元素包含 type, name, scl_code

        流程:
            1. 按依赖顺序排序 (UDT -> DB -> FC/FB/OB)
            2. 逐个调用 import_scl_file 导入
            3. 全部导入完成后编译
            4. 任一步失败时中止并返回错误信息
        """
        blocks: list[dict[str, Any]] = ctx.input.get("blocks", [])
        if not blocks:
            raise ValueError("缺少必填参数: blocks 列表不能为空")

        # 按依赖顺序排序
        sorted_blocks = _sort_blocks_by_dependency(blocks)

        imported_names: list[str] = []
        step_index = 0

        # 逐个导入块
        for i, block in enumerate(sorted_blocks):
            step_index = i + 1
            block_type: str = block.get("type", "")
            block_name: str = block.get("name", "")
            scl_code: str = block.get("scl_code", "")

            if not block_name or not scl_code:
                return {
                    "status": "error",
                    "step": step_index,
                    "detail": f"块 {i} 缺少 name 或 scl_code: name={block_name!r}, scl_code={'<空>' if not scl_code else '<有内容>'}",
                }

            try:
                await ctx.call_async(
                    "tia-mcp.import_scl_file",
                    scl_code=scl_code,
                    block_name=block_name,
                    replace=True,
                )
                imported_names.append(block_name)
            except Exception as e:
                _logger.error(f"步骤 {step_index}: 导入块 {block_name} 失败: {e}")
                return {
                    "status": "error",
                    "step": step_index,
                    "detail": f"导入块 {block_name!r} ({block_type}) 失败: {e}",
                }

        # 全部导入完成后编译
        step_index = len(sorted_blocks) + 1
        try:
            compile_result = await ctx.call_async(
                "plc-mcp-bridge.plc_compile_project",
            )
        except Exception as e:
            _logger.error(f"步骤 {step_index}: 编译失败: {e}")
            return {
                "status": "error",
                "step": step_index,
                "detail": f"编译失败: {e}",
            }

        compile_ok = compile_result.get("ok", compile_result.get("success", False))
        if not compile_ok:
            return {
                "status": "error",
                "step": step_index,
                "detail": f"编译失败: {compile_result.get('errors', '未知错误')}",
            }

        return {
            "status": "ok",
            "total_blocks": len(sorted_blocks),
            "imported": imported_names,
            "compile_ok": True,
        }
