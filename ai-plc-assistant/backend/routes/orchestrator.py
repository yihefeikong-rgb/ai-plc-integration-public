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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from orchestrator.core import WorkflowResult, get_engine
from orchestrator.registry import get_registry
from security import require_local_session
from safety.confirmation import ConfirmationError, ConfirmationService
from orchestrator.safety_gate import get_safety_gate

_logger = logging.getLogger(__name__)

router = APIRouter()
confirmation_service = ConfirmationService()
_CONFIRMABLE_DEVICE_PREFIXES = ("s7:", "modbus:", "melsec:", "opcua:")
_CLIENT_WORKFLOW_TOOL_ALLOWLIST = frozenset({
    "plc-mcp-bridge.s7_read",
    "plc-mcp-bridge.s7_status",
    "opcua-mcp.opcua_read",
    "opcua-mcp.opcua_browse",
    "opcua-mcp.opcua_get_status",
    "modbus-mcp.read_coil",
    "modbus-mcp.read_register",
    "modbus-mcp.read_discrete_input",
    "mitsubishi-mcp.read_device",
    "mitsubishi-mcp.read_devices",
    "robot-mcp.get_status",
})

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


class DynamicWorkflowCreate(BaseModel):
    name: str
    steps: list[dict[str, Any]]


class AdhocRunRequest(BaseModel):
    steps: list[dict[str, Any]]
    input: dict[str, Any] = {}


class ConfirmationRequest(BaseModel):
    operator: str
    target: str
    value: Any
    device_id: str
    ttl_seconds: int = 60


class DynamicWorkflowItem(BaseModel):
    name: str
    steps: int


class DynamicWorkflowListResponse(BaseModel):
    workflows: list[DynamicWorkflowItem]


class DynamicWorkflowDetailResponse(BaseModel):
    name: str
    steps: list[dict[str, Any]]


# ============================================================================
# 辅助
# ============================================================================

_start_time: float = time.time()


def _with_authenticated_operator(input_data: dict[str, Any], actor: str) -> dict[str, Any]:
    """服务端覆盖客户端自报身份，只向编排层传入已认证会话主体。"""
    sanitized = dict(input_data)
    sanitized["authenticated_operator"] = actor
    return sanitized


def _validate_client_steps(steps: list[dict[str, Any]]) -> None:
    """只允许客户端定义明确列出的只读工具，拒绝任意 MCP 工具名。"""
    if not steps or len(steps) > 20:
        raise HTTPException(status_code=422, detail="工作流步骤数必须在 1 到 20 之间")
    for step in steps:
        server = step.get("server")
        tool = step.get("tool")
        params = step.get("params", {})
        if not isinstance(server, str) or not isinstance(tool, str) or not isinstance(params, dict):
            raise HTTPException(status_code=422, detail="工作流步骤格式无效")
        tool_full_name = f"{server}.{tool}"
        if tool_full_name not in _CLIENT_WORKFLOW_TOOL_ALLOWLIST:
            raise HTTPException(status_code=403, detail=f"工具不在客户端工作流白名单中: {tool_full_name}")


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
async def run_workflow(name: str, body: RunWorkflowRequest, actor: str = Depends(require_local_session)) -> WorkflowResultResponse:
    """执行指定工作流"""
    engine = get_engine()
    if name not in engine.list_workflows():
        raise HTTPException(status_code=404, detail=f"未找到工作流: {name}")

    result = await engine.run_async(name, input=_with_authenticated_operator(body.input, actor))

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


# ============================================================================
# 动态工作流
# ============================================================================

@router.get("/workflows/dynamic", response_model=DynamicWorkflowListResponse)
async def list_dynamic_workflows() -> DynamicWorkflowListResponse:
    """列出所有动态工作流"""
    engine = get_engine()
    items = engine.list_dynamic_workflows()
    return DynamicWorkflowListResponse(
        workflows=[DynamicWorkflowItem(**item) for item in items]
    )


@router.get("/workflows/dynamic/{name}", response_model=DynamicWorkflowDetailResponse)
async def get_dynamic_workflow(name: str) -> DynamicWorkflowDetailResponse:
    """获取动态工作流详情"""
    engine = get_engine()
    steps = engine.get_dynamic_workflow(name)
    if steps is None:
        raise HTTPException(status_code=404, detail=f"未找到动态工作流: {name}")
    return DynamicWorkflowDetailResponse(name=name, steps=steps)


@router.post("/workflows/dynamic")
async def save_dynamic_workflow(body: DynamicWorkflowCreate, _: None = Depends(require_local_session)) -> dict[str, str]:
    """创建或更新动态工作流"""
    _validate_client_steps(body.steps)
    engine = get_engine()
    engine.save_dynamic_workflow(body.name, body.steps)
    return {"status": "ok", "name": body.name}


@router.delete("/workflows/dynamic/{name}")
async def delete_dynamic_workflow(name: str, _: None = Depends(require_local_session)) -> dict[str, str]:
    """删除动态工作流"""
    engine = get_engine()
    if not engine.delete_dynamic_workflow(name):
        raise HTTPException(status_code=404, detail=f"未找到动态工作流: {name}")
    return {"status": "ok", "name": name}


@router.post("/workflows/adhoc", response_model=WorkflowResultResponse)
async def run_adhoc(body: AdhocRunRequest, actor: str = Depends(require_local_session)) -> WorkflowResultResponse:
    """执行临时工作流（不保存）"""
    _validate_client_steps(body.steps)
    engine = get_engine()
    result = await engine.run_adhoc(body.steps, input=_with_authenticated_operator(body.input, actor))
    for step in result.steps:
        _record_tool_call(step.tool)
    return _serialize_workflow_result(result)


@router.post("/confirmations")
async def issue_confirmation(
    body: ConfirmationRequest,
    actor: str = Depends(require_local_session),
) -> dict[str, str]:
    """由已鉴权的本地人工会话签发一次性写入确认令牌。"""
    if not body.operator or body.operator in {"human", "local-human", "local-session"}:
        raise HTTPException(status_code=422, detail="确认令牌必须绑定非人工操作者")
    if not body.target or not body.device_id.startswith(_CONFIRMABLE_DEVICE_PREFIXES):
        raise HTTPException(status_code=422, detail="确认令牌目标或设备身份无效")
    if not 1 <= body.ttl_seconds <= 300:
        raise HTTPException(status_code=422, detail="确认令牌有效期必须在 1 到 300 秒之间")

    result = get_safety_gate().check_write(body.target, body.value, operator=body.operator)
    if not result.allowed:
        raise HTTPException(status_code=409, detail=f"安全检查拒绝: {result.reason}")
    if not result.needs_confirmation:
        raise HTTPException(status_code=422, detail="该写入不需要人工确认，不能签发令牌")
    if not result.audit_id:
        raise HTTPException(status_code=503, detail="确认审计记录不可用，拒绝签发令牌")
    try:
        token = confirmation_service.issue(
            operator=body.operator,
            approver=actor,
            target=body.target,
            value=body.value,
            device_id=body.device_id,
            audit_id=result.audit_id,
            ttl_seconds=body.ttl_seconds,
        )
    except ConfirmationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"confirmation_token": token, "audit_id": result.audit_id}
