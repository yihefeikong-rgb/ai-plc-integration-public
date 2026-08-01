"""
TIA 全流水线工作流：跨 plc-mcp-bridge + tia-mcp 的端到端流水线。

步骤:
    1. 创建项目 (plc-mcp-bridge)
    2. 配置硬件 (plc-mcp-bridge)
    3. 生成 SCL 代码 (tia-mcp)
    4. 导入 SCL (tia-mcp)
    5. 编译项目 (plc-mcp-bridge)
    6. 下载到 PLCSIM (plc-mcp-bridge)
"""
from __future__ import annotations

import logging
from typing import Any

from mcp_common.control_target import get_control_target, require_control_ip
from config_loader import cfg as _tia_cfg
from orchestrator.core import WorkflowContext, OrchestratorEngine

_logger = logging.getLogger(__name__)


def build_pipeline_steps(
    project_name: str,
    project_path: str,
    scl_prompt: str,
    plc_ip: str | None = None,
    rack: int | None = None,
    slot: int | None = None,
) -> list[dict[str, Any]]:
    """返回流水线步骤配置列表。

    每步包含:
        - tool: 工具全名 (server.tool_name)
        - args: 工具参数字典
    """
    target = get_control_target()
    require_control_ip(plc_ip or target.plc_ip)
    plc_ip = target.plc_ip
    configured_rack = int(_tia_cfg.simulation.advanced.rack)
    configured_slot = int(_tia_cfg.simulation.advanced.slot)
    if rack is not None and rack != configured_rack:
        raise ValueError("rack 与唯一控制目标配置不一致")
    if slot is not None and slot != configured_slot:
        raise ValueError("slot 与唯一控制目标配置不一致")

    return [
        {
            "tool": "plc-mcp-bridge.plc_create_project",
            "args": {
                "project_name": project_name,
                "parent_directory": project_path,
            },
        },
        {
            "tool": "plc-mcp-bridge.plc_create_instance",
            "args": {},
        },
        {
            "tool": "tia-mcp.generate_scl_code",
            "args": {"description": scl_prompt},
        },
        {
            "tool": "tia-mcp.import_scl_file",
            "args": {
                "scl_code": "",  # 由步骤 3 填充
                "block_name": "",  # 由步骤 3 填充
                "project_path": project_path,
            },
        },
        {
            "tool": "plc-mcp-bridge.plc_compile_project",
            "args": {},
        },
        {
            "tool": "plc-mcp-bridge.plc_download_project",
            "args": {},
        },
    ]


def register_tia_full_pipeline_workflow(engine: OrchestratorEngine) -> None:
    """向编排引擎注册 tia_full_pipeline 工作流"""

    @engine.workflow("tia_full_pipeline")
    async def tia_full_pipeline(ctx: WorkflowContext) -> dict[str, Any]:
        """TIA 全流水线：创建项目 → 配置硬件 → 生成 SCL → 导入 → 编译 → 下载。

        从 ctx.input 读取参数:
            project_name: 项目名称
            project_path: 项目路径
            scl_prompt: SCL 代码生成提示词
            plc_ip/rack/slot: 可选兼容参数，但只能与 config.yaml 的唯一目标一致
        """
        # 校验必填参数
        for key in ("project_name", "project_path", "scl_prompt"):
            if key not in ctx.input:
                raise ValueError(f"缺少必填参数: {key}")

        project_name: str = ctx.input["project_name"]
        project_path: str = ctx.input["project_path"]
        scl_prompt: str = ctx.input["scl_prompt"]
        target = get_control_target()
        require_control_ip(ctx.input.get("plc_ip", target.plc_ip))
        plc_ip = target.plc_ip
        rack = int(_tia_cfg.simulation.advanced.rack)
        slot = int(_tia_cfg.simulation.advanced.slot)
        if "rack" in ctx.input and ctx.input["rack"] != rack:
            raise ValueError("rack 与唯一控制目标配置不一致")
        if "slot" in ctx.input and ctx.input["slot"] != slot:
            raise ValueError("slot 与唯一控制目标配置不一致")

        # 步骤 1: 创建项目
        step1 = await ctx.call_async(
            "plc-mcp-bridge.plc_create_project",
            project_name=project_name,
            parent_directory=project_path,
        )
        project_id = step1.get("project_id", "")

        # 步骤 2: 配置硬件
        step2 = await ctx.call_async(
            "plc-mcp-bridge.plc_create_instance",
        )

        # 步骤 3-5: 生成→导入→编译，编译失败时自动重试（最多 3 次）
        max_retries = 3
        compile_errors_history: list[dict[str, Any]] = []
        step5 = None
        scl_code = ""
        block_name = ""

        for attempt in range(1, max_retries + 1):
            current_prompt = scl_prompt
            if attempt > 1:
                # 构建重试提示词：包含上一次编译错误明细
                error_lines = []
                for err in compile_errors_history:
                    err_line = err.get("line", "?")
                    err_text = err.get("text", err.get("description", "未知错误"))
                    err_file = err.get("file", "unknown")
                    error_lines.append(f"  [第{err_line}行] {err_text}")
                retry_prompt = (
                    "你之前生成的 SCL 有以下编译错误：\n"
                    + "\n".join(error_lines)
                    + "\n\n请修正后重新生成完整 SCL 代码，确保修复上述所有错误。"
                )
                current_prompt = f"{scl_prompt}\n\n{retry_prompt}"
                _logger.info(f"重试 {attempt}/{max_retries}: 编译失败，重新生成 SCL")

            # 步骤 3: 生成 SCL 代码
            step3 = await ctx.call_async(
                "tia-mcp.generate_scl_code",
                description=current_prompt,
            )
            step3_data = step3.get("data", {})
            scl_code = step3.get("scl_code") or step3_data.get("scl_code", "")
            block_name = step3.get("block_name") or step3_data.get("block_name", "")

            # 步骤 4: 导入 SCL
            step4 = await ctx.call_async(
                "tia-mcp.import_scl_file",
                scl_code=scl_code,
                block_name=block_name,
                project_path=project_path,
                replace=True,
            )

            # 步骤 5: 编译项目
            step5 = await ctx.call_async(
                "plc-mcp-bridge.plc_compile_project",
            )

            # 检查编译结果
            compile_result = step5
            compile_success = compile_result.get("success")
            if compile_success is None:
                compile_success = compile_result.get("ok", False)
            # MCP 降级: 如果只有 text 字段且无 success/ok，检查文本是否包含成功指示符
            if not compile_success and "text" in compile_result and "success" not in compile_result and "ok" not in compile_result:
                text_content = str(compile_result["text"]).lower()
                if any(kw in text_content for kw in ("success", "ok", "成功", "0 errors", "0 error", "compilation successful")):
                    compile_success = True
            compile_errors = compile_result.get("error_list") or compile_result.get("errors_list") or []

            if compile_success:
                # 编译通过，跳出重试循环
                _logger.info(f"编译通过（尝试 {attempt}/{max_retries}）")
                compile_errors_history = []
                break
            else:
                # 编译失败，记录错误信息
                if compile_errors:
                    compile_errors_history = compile_errors
                else:
                    # 如果没有 error_list，用基本的错误计数构造
                    compile_errors_history = [
                        {"line": 0, "file": "", "text": f"编译失败：{compile_result.get('errors', '?')} 个错误", "severity": "error"}
                    ]
                _logger.warning(
                    f"编译失败（尝试 {attempt}/{max_retries}）: "
                    f"{len(compile_errors_history)} 个错误"
                )

            if attempt == max_retries:
                # 最后一次也失败了
                return {
                    "status": "error",
                    "project_id": project_id,
                    "project_path": project_path,
                    "scl_code": scl_code,
                    "block_name": block_name,
                    "attempts": max_retries,
                    "all_errors": compile_errors_history,
                    "final_error": f"编译在 {max_retries} 次重试后仍然失败",
                }

        # 步骤 6: 下载到 PLCSIM
        step6 = await ctx.call_async(
            "plc-mcp-bridge.plc_download_project",
        )

        return {
            "status": "success",
            "project_id": project_id,
            "project_path": project_path,
            "scl_code": scl_code,
            "block_name": block_name,
            "compile_ok": step5.get("ok", step5.get("success", False)) if step5 else False,
            "download_ok": step6.get("ok", False),
        }
