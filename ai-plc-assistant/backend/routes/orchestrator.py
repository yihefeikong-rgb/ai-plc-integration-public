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
import os
import re
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from orchestrator.core import WorkflowResult, get_engine
from orchestrator.registry import get_registry
from security import require_local_session
from safety.confirmation import ConfirmationError, ConfirmationService
from safety.confirmation_requests import _confirmation_request_store
from orchestrator.safety_gate import get_safety_gate
from mcp_common.audit import authenticated_actor

_logger = logging.getLogger(__name__)

router = APIRouter()
confirmation_service = ConfirmationService()
_CONFIRMABLE_DEVICE_PREFIXES = ("s7:", "modbus:", "melsec:", "opcua:")
# 设备身份前缀 -> MCP 服务器认证命名空间。服务器侧消费令牌时按
# authenticated_actor(MCP_AUTH_TOKEN, namespace) 派生写入方身份，
# 签发端必须用同一方式推导，否则"绑定操作人"只是一句自报文本。
_DEVICE_NAMESPACE = {
    "modbus:": "modbus",
    "melsec:": "melsec",
    "opcua:": "opcua",
    "s7:": None,  # S7 MCP 暂无会话认证，签发确认令牌将 fail-closed 拒绝
}
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

# 客户端白名单工具的字段级参数 schema。仅允许声明字段，并按类型/范围/
# 长度校验值，防止任意参数值（如 read_register 的超大 count、s7_read
# 的任意 address）直接透传 MCP 只读工具。规则形如:
#   参数名: {"type": 类型, "min"/"max" 整数边界,
#            "min_length"/"max_length"/"pattern" 字符串约束,
#            "item_type"/"min_items"/"max_items" 数组约束}
_CLIENT_WORKFLOW_PARAM_SCHEMAS: dict[str, dict[str, dict[str, Any]]] = {
    "plc-mcp-bridge.s7_read": {
        "address": {"type": str, "min_length": 1, "max_length": 64, "pattern": r"^[A-Za-z0-9._\-]+$"},
    },
    "plc-mcp-bridge.s7_status": {},
    "opcua-mcp.opcua_read": {
        "node_id": {"type": str, "min_length": 1, "max_length": 256},
    },
    "opcua-mcp.opcua_browse": {
        "node_id": {"type": str, "min_length": 1, "max_length": 256},
        "depth": {"type": int, "min": 0, "max": 10},
    },
    "opcua-mcp.opcua_get_status": {},
    "modbus-mcp.read_coil": {
        "address": {"type": int, "min": 0, "max": 65535},
    },
    "modbus-mcp.read_register": {
        "address": {"type": int, "min": 0, "max": 65535},
        "count": {"type": int, "min": 1, "max": 125},
    },
    "modbus-mcp.read_discrete_input": {
        "address": {"type": int, "min": 0, "max": 65535},
    },
    "mitsubishi-mcp.read_device": {
        "addr": {"type": str, "min_length": 1, "max_length": 32},
    },
    "mitsubishi-mcp.read_devices": {
        "addresses": {"type": list, "item_type": str, "min_items": 1, "max_items": 50},
    },
    "robot-mcp.get_status": {},
}

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
    purpose: str = "write"  # write | fuse_reset | workflow
    workflow_name: str = ""  # purpose=workflow 时必填：绑定的危险工作流名称


class ConfirmationRequestCreate(BaseModel):
    """AI 工作流发起的人工审批请求。"""
    workflow_name: str
    description: str = ""
    operator: str = "ai-agent"


def _derive_writer_actor(device_id: str) -> str | None:
    """按设备身份推导写入方的已认证主体（与 MCP 服务器侧派生方式一致）。

    返回 None 表示该设备族无法派生认证身份；签发端必须拒绝签发
    确认令牌，不能回退到调用方自报的 operator。
    """
    for prefix, namespace in _DEVICE_NAMESPACE.items():
        if not device_id.startswith(prefix):
            continue
        if namespace is None:
            # S7 MCP 无设备级命名空间，但配置 MCP_AUTH_TOKEN 时可与服务器侧
            # tools_s7._authenticated_actor() 一致地派生写入方主体（如 s7:<hash>），
            # 从而让确认令牌端到端可用；未配置 token 时仍 fail-closed 拒绝。
            namespace = "s7"
        token = os.environ.get("MCP_AUTH_TOKEN", "")
        if not token:
            raise HTTPException(
                status_code=503,
                detail=f"未配置 MCP_AUTH_TOKEN，无法推导 {namespace} 写入方身份",
            )
        return authenticated_actor(token, namespace)
    return None


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
        _validate_step_params(tool_full_name, params)


def _validate_step_params(tool_full_name: str, params: dict[str, Any]) -> None:
    """按工具的字段级 schema 校验参数；未知参数名或越界值一律 422 拒绝。"""
    schema = _CLIENT_WORKFLOW_PARAM_SCHEMAS.get(tool_full_name, {})
    unknown = set(params) - set(schema)
    if unknown:
        raise HTTPException(status_code=422, detail=f"工具 {tool_full_name} 不允许参数: {sorted(unknown)}")
    for name, rule in schema.items():
        if name not in params:
            continue
        value = params[name]
        param_type = rule["type"]
        if param_type is int:
            if isinstance(value, bool) or not isinstance(value, int):
                raise HTTPException(status_code=422, detail=f"工具 {tool_full_name} 参数 {name} 必须是整数")
            if rule.get("min") is not None and value < rule["min"]:
                raise HTTPException(status_code=422, detail=f"工具 {tool_full_name} 参数 {name} 小于允许最小值 {rule['min']}")
            if rule.get("max") is not None and value > rule["max"]:
                raise HTTPException(status_code=422, detail=f"工具 {tool_full_name} 参数 {name} 大于允许最大值 {rule['max']}")
        elif param_type is str:
            if not isinstance(value, str):
                raise HTTPException(status_code=422, detail=f"工具 {tool_full_name} 参数 {name} 必须是字符串")
            if rule.get("min_length") is not None and len(value) < rule["min_length"]:
                raise HTTPException(status_code=422, detail=f"工具 {tool_full_name} 参数 {name} 过短")
            if rule.get("max_length") is not None and len(value) > rule["max_length"]:
                raise HTTPException(status_code=422, detail=f"工具 {tool_full_name} 参数 {name} 过长")
            pattern = rule.get("pattern")
            if pattern is not None and not re.fullmatch(pattern, value):
                raise HTTPException(status_code=422, detail=f"工具 {tool_full_name} 参数 {name} 格式无效")
        elif param_type is list:
            if not isinstance(value, list):
                raise HTTPException(status_code=422, detail=f"工具 {tool_full_name} 参数 {name} 必须是数组")
            item_type = rule.get("item_type")
            if item_type is not None and not all(isinstance(item, item_type) for item in value):
                raise HTTPException(status_code=422, detail=f"工具 {tool_full_name} 参数 {name} 元素类型无效")
            if rule.get("min_items") is not None and len(value) < rule["min_items"]:
                raise HTTPException(status_code=422, detail=f"工具 {tool_full_name} 参数 {name} 元素数量不足")
            if rule.get("max_items") is not None and len(value) > rule["max_items"]:
                raise HTTPException(status_code=422, detail=f"工具 {tool_full_name} 参数 {name} 元素数量过多")


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
async def health(_: None = Depends(require_local_session)) -> HealthResponse:
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
async def list_workflows(_: None = Depends(require_local_session)) -> WorkflowListResponse:
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
async def list_tools(_: None = Depends(require_local_session)) -> ToolListResponse:
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
async def list_servers(_: None = Depends(require_local_session)) -> ServerListResponse:
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
async def monitor(_: None = Depends(require_local_session)) -> MonitorResponse:
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
async def list_dynamic_workflows(_: None = Depends(require_local_session)) -> DynamicWorkflowListResponse:
    """列出所有动态工作流"""
    engine = get_engine()
    items = engine.list_dynamic_workflows()
    return DynamicWorkflowListResponse(
        workflows=[DynamicWorkflowItem(**item) for item in items]
    )


@router.get("/workflows/dynamic/{name}", response_model=DynamicWorkflowDetailResponse)
async def get_dynamic_workflow(name: str, _: None = Depends(require_local_session)) -> DynamicWorkflowDetailResponse:
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
    """由已鉴权的本地人工会话签发一次性确认令牌。

    purpose=write: 绑定一次变量写入；purpose=fuse_reset: 绑定一次熔断器重置。
    purpose=workflow: 绑定一次危险工作流运行（如 nl_to_plcsim），一次人工批准授权整条危险链。
    写入方身份优先按设备前缀从共享认证密钥派生，不信任调用方自报。
    """
    if not body.operator or body.operator in {"human", "local-human", "local-session"}:
        raise HTTPException(status_code=422, detail="确认令牌必须绑定非人工操作者")
    if not 1 <= body.ttl_seconds <= 300:
        raise HTTPException(status_code=422, detail="确认令牌有效期必须在 1 到 300 秒之间")

    # 工作流级确认：一次人工批准授权一条危险工作流链（编译/下载/启动）。
    # 令牌绑定 workflow_name + device_id=workflow，operator 固定为工作流命名空间，
    # 由编排层工作流入口真实消费（一次运行一个令牌），工具层不再重复验证。
    if body.purpose == "workflow":
        import re as _re
        if not body.workflow_name or not _re.fullmatch(r"[A-Za-z0-9_\-]{1,64}", body.workflow_name):
            raise HTTPException(status_code=422, detail="工作流确认令牌必须提供合法的 workflow_name")
        try:
            token = confirmation_service.issue(
                operator=f"wf:{body.workflow_name}",
                approver=actor,
                target=f"_wf.{body.workflow_name}",
                value="run",
                device_id="workflow",
                audit_id=f"wf-confirm:{body.workflow_name}:{int(time.time())}",
                ttl_seconds=body.ttl_seconds,
            )
        except ConfirmationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"confirmation_token": token, "audit_id": ""}

    if not body.target or not body.device_id.startswith(_CONFIRMABLE_DEVICE_PREFIXES):
        raise HTTPException(status_code=422, detail="确认令牌目标或设备身份无效")
    if body.purpose not in {"write", "fuse_reset"}:
        raise HTTPException(status_code=422, detail="确认令牌用途必须为 write、fuse_reset 或 workflow")

    writer_actor = _derive_writer_actor(body.device_id)
    if writer_actor is None:
        raise HTTPException(
            status_code=503,
            detail="该设备族（S7）无已认证会话，无法验证写入方操作人身份，拒绝签发确认令牌",
        )

    if body.purpose == "fuse_reset":
        namespace = _DEVICE_NAMESPACE.get(
            next((p for p in _CONFIRMABLE_DEVICE_PREFIXES if body.device_id.startswith(p)), "")
        )
        if namespace is None:
            raise HTTPException(status_code=422, detail="该设备族不支持熔断器重置令牌")
        try:
            token = confirmation_service.issue(
                operator=writer_actor,
                approver=actor,
                target=f"{namespace}.fuse_reset",
                value="reset",
                device_id=body.device_id,
                audit_id=f"fuse-reset:{int(time.time())}",
                ttl_seconds=body.ttl_seconds,
            )
        except ConfirmationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"confirmation_token": token, "audit_id": ""}

    result = get_safety_gate().check_write(body.target, body.value, operator=writer_actor)
    if not result.allowed:
        raise HTTPException(status_code=409, detail=f"安全检查拒绝: {result.reason}")
    if not result.needs_confirmation:
        raise HTTPException(status_code=422, detail="该写入不需要人工确认，不能签发令牌")
    if not result.audit_id:
        raise HTTPException(status_code=503, detail="确认审计记录不可用，拒绝签发令牌")
    try:
        token = confirmation_service.issue(
            operator=writer_actor,
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


# ============================================================================
# 人工审批请求队列（AI 发起 → 人工审批 → AI 领取令牌）
# ============================================================================

@router.post("/confirmations/requests")
async def create_confirmation_request(
    body: ConfirmationRequestCreate,
    actor: str = Depends(require_local_session),
) -> dict:
    """AI 侧创建人工审批请求（供编排层工作流调用）。

    返回 request_id，AI 工作流将其返回给用户；人工在审批界面批准后，
    用户重新执行工作流时携带该 request_id 即可领取一次性确认令牌。
    """
    if not body.workflow_name or not re.fullmatch(r"[A-Za-z0-9_\-]{1,64}", body.workflow_name):
        raise HTTPException(status_code=422, detail="workflow_name 不合法")
    record = _confirmation_request_store.create(
        body.workflow_name, body.description, body.operator or "ai-agent")
    return {
        "request_id": record["request_id"],
        "workflow_name": record["workflow_name"],
        "status": record["status"],
        "message": f"已创建人工审批请求 {record['request_id']}，等待人工批准后携带 request_id 重试",
    }


@router.get("/confirmations/requests")
async def list_confirmation_requests(actor: str = Depends(require_local_session)) -> dict:
    """审批界面：列出全部确认请求（未决在前，最新在前）。"""
    return {"requests": _confirmation_request_store.list()}


@router.post("/confirmations/requests/{request_id}/approve")
async def approve_confirmation_request(
    request_id: str, actor: str = Depends(require_local_session),
) -> dict:
    """人工批准：签发一次性工作流级确认令牌（绑定请求记录）。"""
    try:
        return _confirmation_request_store.approve(request_id, actor)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/confirmations/requests/{request_id}/deny")
async def deny_confirmation_request(
    request_id: str, actor: str = Depends(require_local_session),
) -> dict:
    """人工拒绝。"""
    try:
        return _confirmation_request_store.deny(request_id, actor)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/confirmations/requests/{request_id}/token")
async def take_confirmation_token(
    request_id: str, actor: str = Depends(require_local_session),
) -> dict:
    """AI 领取已批准令牌（一次性，领取后即清空）。"""
    token = _confirmation_request_store.take_token(request_id)
    if token is None:
        raise HTTPException(
            status_code=404,
            detail="没有可领取的已批准令牌（请求未批准、已领取或不存在）",
        )
    return {"confirmation_token": token, "request_id": request_id}
