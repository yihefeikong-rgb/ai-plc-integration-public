"""
编排引擎核心 — 工作流注册和同步执行。

支持装饰器风格的工作流定义和同步执行，骨架阶段不引入异步。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from orchestrator.registry import Registry, get_registry

_logger = logging.getLogger(__name__)


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
    """

    input: dict[str, Any] = field(default_factory=dict)
    _registry: Registry | None = None
    _mock_tools: dict[str, Callable] = field(default_factory=dict)
    _steps: list[StepResult] = field(default_factory=list)

    def call(self, tool_full_name: str, **kwargs) -> dict[str, Any]:
        """调用 MCP 工具。

        骨架阶段使用 mock 工具表，后续接入真实 MCP 客户端。
        工具全名格式: "server_name.tool_name"

        Args:
            tool_full_name: 工具全名（如 "tia-mcp.compile_project"）
            **kwargs: 工具参数

        Returns:
            工具返回的字典结果
        """
        import time

        start = time.time()

        try:
            # 检查注册表（可选，仅用于元数据验证）
            if self._registry:
                tool_info = self._registry.get_tool(tool_full_name)
                if tool_info is None:
                    _logger.debug(
                        f"工具 {tool_full_name} 未在注册表中登记，将直接使用 mock 实现"
                    )

            # 使用 mock 工具表执行
            fn = self._mock_tools.get(tool_full_name)
            if fn is None:
                raise RuntimeError(
                    f"工具 {tool_full_name} 没有 mock 实现。"
                    f"请在运行引擎时注册 mock 工具，或接入真实 MCP 客户端。"
                )

            result = fn(**kwargs)
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

        engine.register_mock("server.tool_a", lambda param: {"result": param * 2})
        result = engine.run("my_workflow", input={"key": "value"})
    """

    def __init__(self, registry: Registry | None = None):
        self._workflows: dict[str, Callable] = {}
        self._mock_tools: dict[str, Callable] = {}
        self._registry = registry or get_registry()

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

    def list_workflows(self) -> list[str]:
        """列出所有已注册的工作流"""
        return list(self._workflows.keys())

    def get_workflow(self, name: str) -> Callable | None:
        """按名称获取工作流函数"""
        return self._workflows.get(name)

    def run(
        self,
        workflow_name: str,
        *,
        input: dict[str, Any] | None = None,
        context: WorkflowContext | None = None,
    ) -> WorkflowResult:
        """同步执行一个工作流。

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
            context = WorkflowContext(
                input=input or {},
                _registry=self._registry,
                _mock_tools=self._mock_tools,
            )

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


# 全局单例
_engine = OrchestratorEngine()


def get_engine() -> OrchestratorEngine:
    """获取全局编排引擎单例"""
    return _engine