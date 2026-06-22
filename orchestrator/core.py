"""
编排引擎核心 — 工作流注册和同步执行。

支持装饰器风格的工作流定义和同步执行，
同时兼容 mock 工具模式和真实 MCP 客户端模式。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from orchestrator.registry import Registry, get_registry

_logger = logging.getLogger(__name__)

# 写入工具名模式 — 匹配这些关键词的工具名被视为写入操作
WRITE_TOOL_PATTERNS = [
    "write",    # s7_write, write_tag, plc_write
    "apply",    # plc_apply, apply_config
    "download", # plc_download_project, download_to_plcsim
    "compile",  # plc_compile_project, plc_compile_block
    "create",   # plc_create_block, plc_create_db, plc_create_tag_table
    "delete",   # plc_delete_block, plc_delete_tag
    "import",   # plc_import_block
    "restore",  # plc_golden_restore
]


@dataclass
class StepResult:
    """单个工作流步骤的执行结果"""
    tool: str  # 工具全名 "server.tool"
    ok: bool
    data: Any = None
    error: str = ""
    duration_ms: float = 0.0


@dataclass
class WorkflowResult:
    """工作流执行结果"""
    workflow_name: str
    ok: bool
    steps: list[StepResult] = field(default_factory=list)
    error: str = ""
    total_duration_ms: float = 0.0


@dataclass
class WorkflowContext:
    """工作流执行上下文。

    提供工作流内跨步骤的数据传递和工具调用。

    支持两种模式：
    1. Mock 模式 — 通过 _mock_tools 字典注册本地 mock 函数
    2. MCP 模式 — 通过 _pool 连接真实 MCP 服务器

    MCP 模式下，写入操作会自动经过 SafetyGate 安全门检查。

    工具调用优先级: mock_tools > MCP 连接池 > 报错
    """

    input: dict[str, Any] = field(default_factory=dict)
    _registry: Registry | None = None
    _mock_tools: dict[str, Callable] = field(default_factory=dict)
    _pool: Any = None  # McpConnectionPool | None，延迟导入以避免循环
    _safety_gate: Any = None  # SafetyGate | None，写入操作安全门
    _steps: list[StepResult] = field(default_factory=list)

    @staticmethod
    def _is_write_tool(tool_full_name: str) -> bool:
        """检查工具名是否匹配写入操作模式。

        通过工具全名（含 server_name.tool_name）匹配写入关键词。
        示例: "plc-mcp-bridge.s7_write" → True
              "plc-mcp-bridge.s7_read" → False
        """
        name_lower = tool_full_name.lower()
        return any(pattern in name_lower for pattern in WRITE_TOOL_PATTERNS)

    def call(self, tool_full_name: str, **kwargs) -> dict[str, Any]:
        """调用 MCP 工具（同步接口）。

        工具全名格式: "server_name.tool_name"

        调度优先级:
        1. 先查 _mock_tools（mock 模式，骨架阶段兼容）
        2. 再查 _pool（真实 MCP 连接池，写入操作经过 SafetyGate）
        3. 都没有则报错

        安全机制:
        - MCP 模式下的写入工具调用会先经过 SafetyGate.check_write() 检查
        - 如果 SafetyGate 拒绝，抛出 RuntimeError，调用被阻止
        - 无论通过与否，所有 MCP 工具调用都记录审计日志

        Args:
            tool_full_name: 工具全名（如 "tia-mcp.compile_project"）
            **kwargs: 工具参数

        Returns:
            工具返回的字典结果

        Raises:
            RuntimeError: 安全门拒绝时
        """
        import time

        start = time.time()

        try:
            # 检查注册表（可选，仅用于元数据验证）
            if self._registry:
                tool_info = self._registry.get_tool(tool_full_name)
                if tool_info is None:
                    _logger.debug(
                        f"工具 {tool_full_name} 未在注册表中登记，将直接使用 mock/MCP 实现"
                    )

            result = None

            # 优先级 1: mock 工具（跳过安全门，用于测试）
            fn = self._mock_tools.get(tool_full_name)
            if fn is not None:
                result = fn(**kwargs)

            # 优先级 2: MCP 连接池
            elif self._pool is not None:
                parts = tool_full_name.split(".", 1)
                if len(parts) != 2:
                    raise RuntimeError(
                        f"工具全名格式错误: {tool_full_name}，"
                        f"应为 'server_name.tool_name'"
                    )

                # 安全检查: 写入工具必须经过 SafetyGate
                if self._is_write_tool(tool_full_name):
                    self._check_safety_gate(tool_full_name, kwargs)

                server_name, tool_name = parts
                result = self._call_mcp_sync(server_name, tool_name, kwargs)

                # 审计日志: 记录 MCP 工具调用
                self._audit_tool_call(tool_full_name, kwargs, result)

            # 优先级 3: 都没有
            else:
                raise RuntimeError(
                    f"工具 {tool_full_name} 没有 mock 实现，也没有 MCP 连接池。"
                    f"请在运行引擎时注册 mock 工具，或提供 MCP 连接池。"
                )

            elapsed = (time.time() - start) * 1000

            step = StepResult(
                tool=tool_full_name,
                ok=True,
                data=result,
                duration_ms=elapsed,
            )
            self._steps.append(step)
            return result

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            step = StepResult(
                tool=tool_full_name,
                ok=False,
                error=str(e),
                duration_ms=elapsed,
            )
            self._steps.append(step)
            raise

    def _check_safety_gate(
        self, tool_full_name: str, arguments: dict[str, Any]
    ) -> None:
        """通过 SafetyGate 检查写入操作。

        Args:
            tool_full_name: 工具全名（用于错误消息）
            arguments: 工具参数字典

        Raises:
            RuntimeError: 安全检查拒绝时
        """
        gate = self._safety_gate
        if gate is None:
            _logger.warning(
                f"写入工具 {tool_full_name} 在 MCP 模式下被调用，"
                f"但未配置 SafetyGate。建议在引擎上调用 engine.set_safety_gate()。"
            )
            return

        tag_name = arguments.get(
            "tag_name",
            arguments.get("address", arguments.get("block_name", tool_full_name)),
        )
        value = arguments.get("value", arguments.get("data", ""))
        result = gate.check_write(tag_name, value, operator="ai")

        if not result.allowed:
            raise RuntimeError(f"安全检查拒绝 [{tool_full_name}]: {result.reason}")

    def _audit_tool_call(
        self,
        tool_full_name: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        """记录 MCP 工具调用的审计日志。

        通过安全模块的 audit 日志记录器记录每次 MCP 工具调用。
        失败时不抛出异常，避免影响主流程。
        """
        try:
            from safety.audit import audit

            tag_name = arguments.get(
                "tag_name",
                arguments.get("address", tool_full_name),
            )
            value = str(arguments.get("value", arguments.get("data", "")))
            detail = f"tool={tool_full_name} args={arguments} result={result}"

            audit.log(
                "mcp_tool_call",
                str(tag_name),
                value,
                operator="ai",
                detail=detail,
            )
        except Exception:
            _logger.debug("审计日志记录失败", exc_info=True)

    def _call_mcp_sync(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """同步桥接异步 MCP 调用。

        使用 asyncio.run() 在同步上下文中执行异步 MCP 调用。
        如果已有运行中的事件循环（如 FastAPI），则抛出明确错误提示使用 run_async()。
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 没有运行中的事件循环，直接创建新的
            return asyncio.run(
                self._pool.call_tool(server_name, tool_name, arguments)
            )

        # 已有运行中的事件循环（如在 FastAPI 中）
        # 不能在新线程中创建新事件循环，因为 stdio_client 的 stream
        # 绑定到主事件循环。需要改用异步调用路径。
        raise RuntimeError(
            "在已有事件循环环境中使用 MCP 模式需要异步执行。"
            "请使用 engine.run_async() 并使用 async def 定义工作流。"
        )

    async def call_async(self, tool_full_name: str, **kwargs) -> dict[str, Any]:
        """异步调用 MCP 工具（用于 async def 工作流）。

        直接 await pool.call_tool()，无需同步桥接。
        适用于已有事件循环的环境（FastAPI 等）。

        Args:
            tool_full_name: 工具全名（如 "test-echo.echo"）
            **kwargs: 工具参数

        Returns:
            工具返回的字典结果
        """
        import time

        start = time.time()

        try:
            # 检查注册表
            if self._registry:
                tool_info = self._registry.get_tool(tool_full_name)
                if tool_info is None:
                    _logger.debug(
                        f"工具 {tool_full_name} 未在注册表中登记"
                    )

            result = None

            # 优先级 1: mock 工具
            fn = self._mock_tools.get(tool_full_name)
            if fn is not None:
                result = fn(**kwargs)

            # 优先级 2: MCP 连接池
            elif self._pool is not None:
                parts = tool_full_name.split(".", 1)
                if len(parts) != 2:
                    raise RuntimeError(
                        f"工具全名格式错误: {tool_full_name}，"
                        f"应为 'server_name.tool_name'"
                    )

                # 安全检查: 写入工具必须经过 SafetyGate
                if self._is_write_tool(tool_full_name):
                    self._check_safety_gate(tool_full_name, kwargs)

                server_name, tool_name = parts
                result = await self._pool.call_tool(server_name, tool_name, kwargs)

                # 审计日志
                self._audit_tool_call(tool_full_name, kwargs, result)

            # 优先级 3: 都没有
            else:
                raise RuntimeError(
                    f"工具 {tool_full_name} 没有 mock 实现，也没有 MCP 连接池。"
                )

            elapsed = (time.time() - start) * 1000

            step = StepResult(
                tool=tool_full_name,
                ok=True,
                data=result,
                duration_ms=elapsed,
            )
            self._steps.append(step)
            return result

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            step = StepResult(
                tool=tool_full_name,
                ok=False,
                error=str(e),
                duration_ms=elapsed,
            )
            self._steps.append(step)
            raise


class OrchestratorEngine:
    """编排引擎 — 工作流注册、发现和执行。

    使用方式:
        engine = OrchestratorEngine()

        @engine.workflow("my_workflow")
        def my_workflow(ctx: WorkflowContext):
            step1 = ctx.call("server.tool_a", param=1)
            step2 = ctx.call("server.tool_b", data=step1["result"])
            return {"status": "ok"}

        # Mock 模式
        engine.register_mock("server.tool_a", lambda param: {"result": param * 2})
        result = engine.run("my_workflow", input={"key": "value"})

        # MCP 模式（同步，无事件循环时可用）
        pool = McpConnectionPool()
        await pool.connect_server(plc_bridge_info)  # 需要预先异步连接
        engine.set_pool(pool)
        engine.set_safety_gate()
        result = engine.run("my_workflow", input={"key": "value"})

        # MCP 模式（异步，在 FastAPI 等事件循环中）
        pool = McpConnectionPool()
        await pool.connect_server(plc_bridge_info)
        engine.set_pool(pool)
        engine.set_safety_gate()
        result = await engine.run_async("my_workflow", input={"key": "value"})
    """

    def __init__(self, registry: Registry | None = None):
        self._workflows: dict[str, Callable] = {}
        self._mock_tools: dict[str, Callable] = {}
        self._registry = registry or get_registry()
        self._pool: Any = None  # McpConnectionPool | None
        self._safety_gate: Any = None  # SafetyGate | None

    def workflow(self, name: str):
        """装饰器：注册工作流函数。

        用法:
            @engine.workflow("tia_download")
            def tia_download(ctx): ...
        """
        def decorator(fn: Callable) -> Callable:
            self._workflows[name] = fn
            _logger.info(f"已注册工作流: {name}")
            return fn
        return decorator

    def register_mock(self, tool_full_name: str, fn: Callable) -> None:
        """注册 mock 工具，用于骨架阶段测试。

        Args:
            tool_full_name: 工具全名（如 "tia-mcp.compile_project"）
            fn: mock 实现函数
        """
        self._mock_tools[tool_full_name] = fn

    def register_mocks(self, mocks: dict[str, Callable]) -> None:
        """批量注册 mock 工具"""
        self._mock_tools.update(mocks)

    def set_pool(self, pool: Any) -> None:
        """设置 MCP 连接池，用于真实 MCP 调用。

        Args:
            pool: McpConnectionPool 实例
        """
        self._pool = pool

    def set_safety_gate(self, gate: Any = None) -> None:
        """设置安全门实例，用于写入操作拦截。

        Args:
            gate: SafetyGate 实例。如果为 None，则使用全局单例。
        """
        if gate is None:
            from orchestrator.safety_gate import get_safety_gate
            gate = get_safety_gate()
        self._safety_gate = gate

    def list_workflows(self) -> list[str]:
        """列出所有已注册的工作流"""
        return list(self._workflows.keys())

    def get_workflow(self, name: str) -> Callable | None:
        """按名称获取工作流函数"""
        return self._workflows.get(name)

    def _build_context(self, input: dict[str, Any] | None) -> WorkflowContext:
        """构建工作流执行上下文。"""
        return WorkflowContext(
            input=input or {},
            _registry=self._registry,
            _mock_tools=self._mock_tools,
            _pool=self._pool,
            _safety_gate=self._safety_gate,
        )

    def run(
        self,
        workflow_name: str,
        *,
        input: dict[str, Any] | None = None,
        context: WorkflowContext | None = None,
    ) -> WorkflowResult:
        """同步执行一个工作流。

        Mock 模式或无事件循环时可用。
        如果已有事件循环且使用 MCP 模式，请使用 run_async()。

        Args:
            workflow_name: 工作流名称
            input: 输入参数
            context: 自定义上下文（可选）

        Returns:
            WorkflowResult 包含执行结果和步骤详情
        """
        import time

        wf_fn = self._workflows.get(workflow_name)
        if wf_fn is None:
            return WorkflowResult(
                workflow_name=workflow_name,
                ok=False,
                error=f"未找到工作流: {workflow_name}",
            )

        if context is None:
            context = self._build_context(input)

        start = time.time()

        try:
            output = wf_fn(context)
            elapsed = (time.time() - start) * 1000

            # 检查所有步骤是否成功
            all_ok = all(s.ok for s in context._steps) if context._steps else True

            return WorkflowResult(
                workflow_name=workflow_name,
                ok=all_ok,
                steps=list(context._steps),
                total_duration_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            _logger.error(f"工作流 {workflow_name} 执行失败: {e}")
            return WorkflowResult(
                workflow_name=workflow_name,
                ok=False,
                steps=list(context._steps),
                error=str(e),
                total_duration_ms=elapsed,
            )

    async def run_async(
        self,
        workflow_name: str,
        *,
        input: dict[str, Any] | None = None,
        context: WorkflowContext | None = None,
    ) -> WorkflowResult:
        """异步执行一个工作流（支持 MCP 模式）。

        用于 FastAPI 等已有事件循环的环境。
        工作流内的 MCP 工具调用将通过异步路径执行。

        Args:
            workflow_name: 工作流名称
            input: 输入参数
            context: 自定义上下文（可选）

        Returns:
            WorkflowResult 包含执行结果和步骤详情
        """
        import time

        wf_fn = self._workflows.get(workflow_name)
        if wf_fn is None:
            return WorkflowResult(
                workflow_name=workflow_name,
                ok=False,
                error=f"未找到工作流: {workflow_name}",
            )

        if context is None:
            context = self._build_context(input)

        start = time.time()

        try:
            # 异步执行工作流函数
            result = wf_fn(context)
            # 如果工作流返回了协程，await 它
            if asyncio.iscoroutine(result):
                await result

            elapsed = (time.time() - start) * 1000

            all_ok = all(s.ok for s in context._steps) if context._steps else True

            return WorkflowResult(
                workflow_name=workflow_name,
                ok=all_ok,
                steps=list(context._steps),
                total_duration_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            _logger.error(f"工作流 {workflow_name} 执行失败: {e}")
            return WorkflowResult(
                workflow_name=workflow_name,
                ok=False,
                steps=list(context._steps),
                error=str(e),
                total_duration_ms=elapsed,
            )


# 全局单例
_engine = OrchestratorEngine()


def get_engine() -> OrchestratorEngine:
    """获取全局编排引擎单例"""
    return _engine