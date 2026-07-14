"""全链路 Pipeline API。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from orchestrator.core import StepResult, WorkflowResult, get_engine
from orchestrator.workflows.nl_to_plcsim_pipeline import (
    DEFAULT_ACCEPTANCE_PROMPT,
    register_nl_to_plcsim_pipeline_workflow,
)
from security import require_local_session

router = APIRouter()

WORKFLOW_NAME = "nl_to_plcsim_pipeline"

STEP_NAMES = {
    "tia-mcp.create_ladder_block": "生成梯形图块",
    "tia-mcp.call_fb_in_ob1": "接入 OB1 调用链",
    "plc-mcp-bridge.plc_compile_project": "编译 TIA 项目",
    "plc-mcp-bridge.plc_download_project": "下载到 PLCSIM",
    "plc-mcp-bridge.s7_connect": "连接 PLCSIM",
    "plc-mcp-bridge.s7_read": "snap7 回读验证",
    "plc-mcp-bridge.s7_disconnect": "断开 S7 连接",
    "plc-mcp-bridge.plc_fio_write_config": "写入 Factory I/O 配置",
    "plc-mcp-bridge.plc_fio_launch": "启动 Factory I/O",
}


class NlToSimRequest(BaseModel):
    model_config = {"extra": "forbid"}

    description: str = DEFAULT_ACCEPTANCE_PROMPT
    block_name: str = "AutoGen"
    launch_fio: bool = False


def _step_payload(step: StepResult) -> dict[str, Any]:
    return {
        "name": STEP_NAMES.get(step.tool, step.tool),
        "tool": step.tool,
        "status": "PASS" if step.ok else "FAIL",
        "detail": step.data if step.ok else step.error,
        "duration_ms": step.duration_ms,
    }


def _snap7_summary(result: WorkflowResult) -> dict[str, Any]:
    read_step = next((s for s in result.steps if s.tool == "plc-mcp-bridge.s7_read" and s.ok), None)
    return {
        "verified": result.ok and read_step is not None,
        "readback": read_step.data if read_step else "",
    }


def _generation_summary(result: WorkflowResult) -> dict[str, Any]:
    step = next((s for s in result.steps if s.tool == "tia-mcp.create_ladder_block" and s.ok), None)
    data = step.data if step and isinstance(step.data, dict) else {}
    return {
        "block_name": data.get("blockName") or data.get("block_name", ""),
        "networks": data.get("networks", 0),
        "xml_path": data.get("xmlPath", ""),
    }


def _ensure_workflow_registered() -> None:
    engine = get_engine()
    if WORKFLOW_NAME not in engine.list_workflows():
        register_nl_to_plcsim_pipeline_workflow(engine)


@router.post("/nl-to-sim")
async def run_nl_to_sim(
    req: NlToSimRequest,
    actor: str = Depends(require_local_session),
) -> dict[str, Any]:
    """自然语言需求 → TIA/PLCSIM/FIO 主链入口。"""
    if not req.description.strip():
        raise HTTPException(status_code=400, detail="请输入自然语言控制需求")

    _ensure_workflow_registered()
    engine = get_engine()
    result = await engine.run_async(
        WORKFLOW_NAME,
        input={
            "description": req.description,
            "block_name": req.block_name,
            "launch_fio": req.launch_fio,
            "authenticated_operator": actor,
        },
    )

    return {
        "workflow_name": result.workflow_name,
        "ok": result.ok,
        "error": result.error,
        "steps": [_step_payload(step) for step in result.steps],
        "generation": _generation_summary(result),
        "snap7": _snap7_summary(result),
        "total_duration_ms": result.total_duration_ms,
    }
