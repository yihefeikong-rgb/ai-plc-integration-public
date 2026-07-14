"""
编排层 FastAPI HTTP API

提供 HTTP 接口访问编排引擎的工作流、工具和服务器。
"""
from __future__ import annotations

import logging
import hashlib
import hmac
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from orchestrator.bootstrap import bootstrap, shutdown
from orchestrator.core import WorkflowResult, get_engine
from orchestrator.mcp_owner import McpOwnerBusyError, McpOwnerLock
from orchestrator.mcp_pool import McpConnectionPool
from orchestrator.registry import get_registry

_logger = logging.getLogger(__name__)

# 模块级连接池，供 lifespan 管理
_pool: McpConnectionPool | None = None


async def require_local_session(x_local_api_token: str | None = Header(default=None)) -> str:
    """独立编排 API 的本地控制鉴权，未配置令牌时失败关闭。"""
    expected = os.environ.get("LOCAL_API_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503, detail="本地控制未配置 LOCAL_API_TOKEN")
    if not x_local_api_token or not hmac.compare_digest(x_local_api_token, expected):
        raise HTTPException(status_code=401, detail="本地控制会话令牌无效")
    fingerprint = hashlib.sha256(x_local_api_token.encode("utf-8")).hexdigest()[:16]
    return f"local-session:{fingerprint}"


# ============================================================================
# 请求/响应模型
# ============================================================================

class RunWorkflowRequest(BaseModel):
    """工作流执行请求"""
    input: dict[str, Any] = Field(default_factory=dict)


class StepResultResponse(BaseModel):
    """步骤结果响应"""
    tool: str
    ok: bool
    data: Any = None
    error: str = ""
    duration_ms: float = 0.0


class WorkflowResultResponse(BaseModel):
    """工作流执行结果响应"""
    workflow_name: str
    ok: bool
    steps: list[StepResultResponse]
    error: str | None = None
    total_duration_ms: float


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    servers_connected: int
    workflows: int
    tools: int


class WorkflowListResponse(BaseModel):
    """工作流列表响应"""
    workflows: list[str]


class ToolItemResponse(BaseModel):
    """工具项响应"""
    name: str
    server: str
    category: str
    description: str


class ToolListResponse(BaseModel):
    """工具列表响应"""
    tools: list[ToolItemResponse]


class ServerItemResponse(BaseModel):
    """服务器项响应"""
    name: str
    description: str
    tool_count: int


class ServerListResponse(BaseModel):
    """服务器列表响应"""
    servers: list[ServerItemResponse]


# ============================================================================
# 辅助函数
# ============================================================================

def _serialize_workflow_result(result: WorkflowResult) -> WorkflowResultResponse:
    """将 WorkflowResult 序列化为响应模型"""
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
# 生命周期
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时 bootstrap，关闭时 shutdown"""
    global _pool
    owner_lock = McpOwnerLock("standalone-orchestrator")
    try:
        owner_lock.acquire()
    except McpOwnerBusyError as exc:
        _logger.error("MCP 所有者冲突: %s", exc)
        raise

    _pool = McpConnectionPool()
    try:
        await bootstrap(pool=_pool, engine=get_engine())
        _logger.info("编排层 HTTP API 启动完成")
    except Exception as e:
        _logger.error(f"编排层启动失败: {e}")
        _pool = None
        owner_lock.release()
        raise
    try:
        yield
    finally:
        try:
            await shutdown(pool=_pool)
            _logger.info("编排层 HTTP API 已关闭")
        except Exception as e:
            _logger.error(f"编排层关闭失败: {e}")
        finally:
            _pool = None
            owner_lock.release()


# ============================================================================
# FastAPI 应用
# ============================================================================

app = FastAPI(
    title="AI PLC Orchestrator",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
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


@app.get("/workflows", response_model=WorkflowListResponse)
async def list_workflows() -> WorkflowListResponse:
    """列出所有已注册工作流"""
    engine = get_engine()
    return WorkflowListResponse(workflows=engine.list_workflows())


@app.post("/workflows/{name}/run", response_model=WorkflowResultResponse)
async def run_workflow(
    name: str,
    body: RunWorkflowRequest,
    actor: str = Depends(require_local_session),
) -> WorkflowResultResponse:
    """执行指定工作流"""
    engine = get_engine()
    if name not in engine.list_workflows():
        raise HTTPException(status_code=404, detail=f"未找到工作流: {name}")

    input_data = dict(body.input)
    # 不能信任 HTTP body 中自报的 operator；审计仅接受鉴权层生成的指纹。
    input_data["authenticated_operator"] = actor
    result = await engine.run_async(name, input=input_data)
    return _serialize_workflow_result(result)


@app.get("/tools", response_model=ToolListResponse)
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


@app.get("/servers", response_model=ServerListResponse)
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
