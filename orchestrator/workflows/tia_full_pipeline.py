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

from orchestrator.core import WorkflowContext, OrchestratorEngine

_logger = logging.getLogger(__name__)


def build_pipeline_steps(
    project_name: str,
    project_path: str,
    scl_prompt: str,
    plc_ip: str = "192.168.0.110",
    rack: int = 0,
    slot: int = 1,
) -> list[dict[str, Any]]:
    """返回流水线步骤配置列表。

    每步包含:
        - tool: 工具全名 (server.tool_name)
        - args: 工具参数字典
    """
    return [
        {
            "tool": "plc-mcp-bridge.plc_create_project",
            "args": {"name": project_name, "path": project_path},
        },
        {
            "tool": "plc-mcp-bridge.plc_create_instance",
            "args": {
                "project_path": project_path,
                "plc_ip": plc_ip,
                "rack": rack,
                "slot": slot,
            },
        },
        {
            "tool": "tia-mcp.generate_scl_code",
            "args": {"prompt": scl_prompt},
        },
        {
            "tool": "tia-mcp.import_scl_file",
            "args": {
                "scl_path": "",  # 由步骤 3 填充
                "project_path": project_path,
            },
        },
        {
            "tool": "plc-mcp-bridge.plc_compile_project",
            "args": {"project_path": project_path},
        },
        {
            "tool": "plc-mcp-bridge.plc_download_project",
            "args": {"project_path": project_path, "plc_ip": plc_ip},
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
            plc_ip: PLC IP 地址（默认 192.168.0.110）
            rack: PLC 机架号（默认 0）
            slot: PLC 槽号（默认 1）
        """
        # 校验必填参数
        for key in ("project_name", "project_path", "scl_prompt"):
            if key not in ctx.input:
                raise ValueError(f"缺少必填参数: {key}")

        project_name: str = ctx.input["project_name"]
        project_path: str = ctx.input["project_path"]
        scl_prompt: str = ctx.input["scl_prompt"]
        plc_ip: str = ctx.input.get("plc_ip", "192.168.0.110")
        rack: int = ctx.input.get("rack", 0)
        slot: int = ctx.input.get("slot", 1)

        # 步骤 1: 创建项目
        step1 = await ctx.call_async(
            "plc-mcp-bridge.plc_create_project",
            name=project_name,
            path=project_path,
        )
        project_id = step1.get("project_id", "")

        # 步骤 2: 配置硬件
        step2 = await ctx.call_async(
            "plc-mcp-bridge.plc_create_instance",
            project_path=project_path,
            plc_ip=plc_ip,
            rack=rack,
            slot=slot,
        )

        # 步骤 3: 生成 SCL 代码
        step3 = await ctx.call_async(
            "tia-mcp.generate_scl_code",
            prompt=scl_prompt,
        )
        scl_path = step3.get("scl_path", "")

        # 步骤 4: 导入 SCL
        step4 = await ctx.call_async(
            "tia-mcp.import_scl_file",
            scl_path=scl_path,
            project_path=project_path,
        )

        # 步骤 5: 编译项目
        step5 = await ctx.call_async(
            "plc-mcp-bridge.plc_compile_project",
            project_path=project_path,
        )

        # 步骤 6: 下载到 PLCSIM
        step6 = await ctx.call_async(
            "plc-mcp-bridge.plc_download_project",
            project_path=project_path,
            plc_ip=plc_ip,
        )

        return {
            "status": "success",
            "project_id": project_id,
            "project_path": project_path,
            "scl_path": scl_path,
            "compile_ok": step5.get("ok", False),
            "download_ok": step6.get("ok", False),
        }
