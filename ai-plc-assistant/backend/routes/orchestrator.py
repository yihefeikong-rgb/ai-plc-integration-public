"""编排层路由 — 将 orchestrator 包的功能暴露为 FastAPI Router。

端点：
  GET  /health         健康检查
  GET  /workflows      工作流列表
  POST /workflows/{name}/run  执行工作流
  GET  /tools          工具列表（含分类）
  GET  /servers        服务器列表
  GET  /monitor        实时状态监控
"""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from orchestrator.core import WorkflowResult, get_engine
from orchestrator.registry import get_registry

_logger = logging.getLogger(__name__)

router = APIRouter()

# 工具调用计数器（模块级，进程内有效）
_tool_call_counts: dict[str, int] = {}


def _record_tool_call(tool_name: str) -> None:
    _tool_call_counts[tool_name] = _tool_call_counts.get(tool_name, 0) + 1


# ============================================================================
# 请求/响应模型
# ============================================================================

class RunWorkflowRequest(BaseModel):
    input: dict[str, Any] = {}


class StepResultResponse(BaseModel):
    tool: str
    ok: bool
    data: Any = None
    error: str = ""
    duration_ms: float = 0.0


class WorkflowResultResponse(BaseModel):
    workflow_name: str
    ok: bool
    steps: list[StepResultResponse]
    error: str | None = None
    total_duration_ms: float


class HealthResponse(BaseModel):
    status: str
    servers_connected: int
    workflows: int
    tools: int


class WorkflowListResponse(BaseModel):
    workflows: list[str]


class ToolItemResponse(BaseModel):
    name: str
    server: str
    category: str
    description: str


class ToolListResponse(BaseModel):
    tools: list[ToolItemResponse]


class ServerItemResponse(BaseModel):
    name: str
    description: str
    tool_count: int


class ServerListResponse(BaseModel):
    servers: list[ServerItemResponse]


class MonitorResponse(BaseModel):
    servers_connected: int
    active_workflows: int
    total_tools: int
    tool_call_counts: dict[str, int]
    uptime_seconds: float


# ============================================================================
# 辅助
# ============================================================================

_start_time: float = time.time()


def _serialize_workflow_result(result: WorkflowResult) -> WorkflowResultResponse:
    steps = [
        StepResultResponse(
            tool=step.tool,
            ok=step.ok,
            data=step.data,
            error=step.error,
            duration_ms=step.duration_ms,
        )
        for step in result.steps
    ]
    return WorkflowResultResponse(
        workflow_name=result.workflow_name,
        ok=result.ok,
        steps=steps,
        error=result.error if result.error else None,
        total_duration_ms=result.total_duration_ms,
    )


# ============================================================================
# 端点
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """健康检查"""
    registry = get_registry()
    engine = get_engine()
    return HealthResponse(
        status="ok",
        servers_connected=registry.server_count(),
        workflows=len(engine.list_workflows()),
        tools=registry.tool_count(),
    )


@router.get("/workflows", response_model=WorkflowListResponse)
async def list_workflows() -> WorkflowListResponse:
    """列出所有已注册工作流"""
    engine = get_engine()
    return WorkflowListResponse(workflows=engine.list_workflows())


@router.post("/workflows/{name}/run", response_model=WorkflowResultResponse)
async def run_workflow(name: str, body: RunWorkflowRequest) -> WorkflowResultResponse:
    """执行指定工作流"""
    engine = get_engine()
    if name not in engine.list_workflows():
        raise HTTPException(status_code=404, detail=f"未找到工作流: {name}")

    result = await engine.run_async(name, input=body.input)

    # 记录工具调用
    for step in result.steps:
        _record_tool_call(step.tool)

    return _serialize_workflow_result(result)


@router.get("/tools", response_model=ToolListResponse)
async def list_tools() -> ToolListResponse:
    """列出所有可用工具"""
    registry = get_registry()
    tools = registry.list_tools()
    items = [
        ToolItemResponse(
            name=tool.name,
            server=tool.server,
            category=tool.category,
            description=tool.description,
        )
        for tool in tools
    ]
    return ToolListResponse(tools=items)


@router.get("/servers", response_model=ServerListResponse)
async def list_servers() -> ServerListResponse:
    """列出所有已连接服务器"""
    registry = get_registry()
    server_names = registry.list_servers()
    items = []
    for sname in server_names:
        server_info = registry.get_server(sname)
        items.append(
            ServerItemResponse(
                name=sname,
                description=server_info.description if server_info else "",
                tool_count=len(server_info.tools) if server_info else 0,
            )
        )
    return ServerListResponse(servers=items)


@router.get("/monitor", response_model=MonitorResponse)
async def monitor() -> MonitorResponse:
    """实时状态监控"""
    registry = get_registry()
    engine = get_engine()
    return MonitorResponse(
        servers_connected=registry.server_count(),
        active_workflows=len(engine.list_workflows()),
        total_tools=registry.tool_count(),
        tool_call_counts=dict(_tool_call_counts),
        uptime_seconds=round(time.time() - _start_time, 2),
    )
