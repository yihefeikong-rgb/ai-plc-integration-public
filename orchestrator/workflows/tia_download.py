"""
示例工作流：TIA 代码生成 → 导入 → 编译 → 下载。

这是一个跨 MCP 服务器的端到端工作流，演示编排层的核心能力：
- 步骤间的数据传递
- 失败时的部分步骤记录
- 与安全门的集成点
"""
from __future__ import annotations

from orchestrator.core import WorkflowContext, OrchestratorEngine


def register_tia_download_workflow(engine: OrchestratorEngine) -> None:
    """向编排引擎注册 tia_download 工作流"""

    @engine.workflow("tia_download")
    def tia_download_workflow(ctx: WorkflowContext) -> dict:
        """TIA 代码生成 → 导入 SCL → 编译 → 下载到 PLCSIM

        步骤:
            1. generate_scl_code — 使用 AI 生成 SCL 代码
            2. import_scl_file — 将 SCL 文件导入 TIA 项目
            3. compile_project — 编译整个项目
            4. download_to_plcsim — 下载到 PLCSIM 仿真器

        Args:
            ctx.input["prompt"]: AI 提示词（如 "生成电机控制 FB"）
            ctx.input["project_path"]: TIA 项目路径
            ctx.input["plc_ip"]: PLC/PLCSIM IP 地址
        """
        # 步骤 1: 生成 SCL 代码
        step1 = ctx.call(
            "tia-mcp.generate_scl_code",
            prompt=ctx.input.get("prompt", "生成电机控制 FB"),
        )

        # 步骤 2: 导入 SCL 文件
        step2 = ctx.call(
            "tia-mcp.import_scl_file",
            scl_path=step1.get("scl_path", ""),
            project_path=ctx.input.get("project_path", ""),
        )

        # 步骤 3: 编译项目
        step3 = ctx.call(
            "tia-mcp.compile_project",
            project_path=ctx.input.get("project_path", ""),
        )

        # 步骤 4: 下载到 PLCSIM
        step4 = ctx.call(
            "tia-mcp.download_to_plcsim",
            project_path=ctx.input.get("project_path", ""),
            plc_ip=ctx.input.get("plc_ip", "192.168.0.110"),
        )

        return {
            "status": "success",
            "scl_path": step1.get("scl_path", ""),
            "blocks_imported": step2.get("blocks_imported", 0),
            "compile_ok": step3.get("ok", False),
            "download_ok": step4.get("ok", False),
        }