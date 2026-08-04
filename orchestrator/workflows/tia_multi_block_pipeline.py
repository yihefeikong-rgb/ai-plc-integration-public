"""
多块依赖顺序工作流：按依赖顺序导入多个 PLC 程序块。

依赖顺序:
    UDT(1) -> 变量表(2) -> 全局DB(3) -> FC/FB/OB(4) -> 实例DB(5) -> 编译(6)

输入格式:
    {
      "blocks": [
        {"type": "UDT", "name": "MotorParams", "scl_code": "TYPE \"MotorParams\"\n..."},
        {"type": "DB", "name": "DB_Process", "scl_code": "DATA_BLOCK \"DB_Process\"\n..."},
        {"type": "FB", "name": "MotorCtrl", "scl_code": "FUNCTION_BLOCK \"MotorCtrl\"\n..."}
      ],
      "confirmation_token": "人工确认令牌（真实 MCP 连接池下必填）"
    }

安全约束:
    - 只接受 blocks/confirmation_token 两个输入字段，其余一律拒绝
    - 每块 type 必须在允许集合内，name 必须是合法 IEC 标识符
    - 每块 scl_code 必须通过 scl_lint 静态校验，违规即拒绝
    - 真实 MCP 连接池（工程态写操作）必须携带 confirmation_token
"""
from __future__ import annotations

import importlib.util
import logging
import re
from pathlib import Path
from typing import Any

from orchestrator.core import WorkflowContext, OrchestratorEngine
from orchestrator.mcp_pool import McpConnectionPool

_logger = logging.getLogger(__name__)

# 允许的工作流输入字段；其余字段一律拒绝（防止注入无关参数）。
_ALLOWED_INPUT_FIELDS = frozenset({"blocks", "confirmation_token", "confirmation_request_id"})

# TIA 块名约束: IEC 61131-3 标识符（字母/下划线开头，字母/数字/下划线，最长 128 字符）。
_BLOCK_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")

# 允许导入的块类型；COMPILE 是工作流阶段，不是可导入的块。
_IMPORTABLE_BLOCK_TYPES = frozenset({"UDT", "TAG_TABLE", "DB", "FC", "FB", "OB", "INSTANCE_DB"})

# 单块 SCL 上限 4 MiB，防止超长内容滥用。
_MAX_SCL_CODE_LENGTH = 4 * 1024 * 1024


def _load_scl_lint() -> Any | None:
    """加载 tia-mcp 同款 scl_lint.lint_scl 静态校验器。

    scl_lint 位于 mcp-servers/tia-mcp/ 下，运行时不保证在 sys.path 中；
    这里用 importlib 按文件路径加载，避免修改进程级 sys.path。
    """
    tia_mcp_dir = Path(__file__).resolve().parent.parent.parent / "mcp-servers" / "tia-mcp"
    scl_lint_path = tia_mcp_dir / "scl_lint.py"
    if not scl_lint_path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("scl_lint", scl_lint_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "lint_scl", None)


# 模块加载时解析一次；不可用时工作流 fail-closed 拒绝导入。
_SCL_LINT = _load_scl_lint()

# 依赖排序权重: 数字越小越先执行
_ORDER_WEIGHT: dict[str, int] = {
    "UDT": 1,
    "TAG_TABLE": 2,
    "DB": 3,          # 全局 DB
    "FC": 4,
    "FB": 4,
    "OB": 4,
    "INSTANCE_DB": 5,
    "COMPILE": 6,
}


def _sort_blocks_by_dependency(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按依赖顺序排序块列表。

    UDT -> 变量表 -> 全局DB -> FC/FB/OB -> 实例DB
    """
    return sorted(blocks, key=lambda b: _ORDER_WEIGHT.get(b.get("type", "").upper(), 99))


def _validate_block_input(i: int, block: dict[str, Any]) -> None:
    """校验单块输入（type/name 约束 + SCL 静态 lint）；任一不合规即 fail-closed。

    i 为块在输入列表中的序号（用于错误定位）。
    """
    block_name = block.get("name", "")
    scl_code = block.get("scl_code", "")

    if not block_name or not scl_code:
        raise ValueError(
            f"块 {i} 缺少 name 或 scl_code: "
            f"name={block_name!r}, scl_code={'<空>' if not scl_code else '<有内容>'}"
        )
    if not isinstance(block_name, str) or not _BLOCK_NAME_RE.match(block_name):
        raise ValueError(
            f"块 {i} 的 name {block_name!r} 不是合法的 TIA 块名"
            f"（仅允许字母/数字/下划线，字母或下划线开头，最长 128 字符）"
        )
    block_type = str(block.get("type", "")).strip().upper()
    if block_type not in _IMPORTABLE_BLOCK_TYPES:
        raise ValueError(
            f"块 {i} 的 type {block_type!r} 不是可导入的块类型"
            f"（允许: {', '.join(sorted(_IMPORTABLE_BLOCK_TYPES))}）"
        )
    if not isinstance(scl_code, str) or not scl_code.strip():
        raise ValueError(f"块 {i} 的 scl_code 必须是非空字符串")
    if len(scl_code) > _MAX_SCL_CODE_LENGTH:
        raise ValueError(f"块 {i} 的 scl_code 超过 {_MAX_SCL_CODE_LENGTH} 字符上限")
    if _SCL_LINT is None:
        raise RuntimeError("SCL 静态校验器 (scl_lint) 不可用，拒绝导入")
    lint_errors = _SCL_LINT(scl_code)
    if lint_errors:
        first = lint_errors[0]
        raise ValueError(
            f"块 {block_name!r} 的 SCL 静态校验发现 {len(lint_errors)} 个违规，"
            f"已阻止导入（首条: {first.get('rule', '?')} 第{first.get('line', '?')}行: "
            f"{first.get('message', '')}）"
        )


def register_tia_multi_block_pipeline_workflow(engine: OrchestratorEngine) -> None:
    """向编排引擎注册 tia_multi_block_pipeline 工作流"""

    @engine.workflow("tia_multi_block_pipeline")
    async def tia_multi_block_pipeline(ctx: WorkflowContext) -> dict[str, Any]:
        """按依赖顺序导入多个 PLC 程序块。

        从 ctx.input 读取参数:
            blocks: 块列表，每个元素包含 type, name, scl_code
            confirmation_token: 人工确认令牌（真实 MCP 连接池下必填）

        流程:
            1. 按依赖顺序排序 (UDT -> DB -> FC/FB/OB)
            2. 逐个调用 import_scl_file 导入
            3. 全部导入完成后编译
            4. 任一步失败时中止并抛出可审计错误
        """
        blocks: list[dict[str, Any]] = ctx.input.get("blocks", [])
        unsupported = sorted(set(ctx.input) - _ALLOWED_INPUT_FIELDS)
        if unsupported:
            raise ValueError(f"不支持的工作流参数: {', '.join(unsupported)}")
        if not isinstance(blocks, list):
            raise ValueError("blocks 必须是列表")
        if not blocks:
            raise ValueError("缺少必填参数: blocks 列表不能为空")
        for i, block in enumerate(blocks):
            if not isinstance(block, dict):
                raise ValueError(f"块 {i} 必须是对象（包含 type/name/scl_code）")

        # 工程态控制操作（replace 导入 + 编译）必须由人工确认令牌真实授权：
        # 编排层在入口消费一次性工作流级确认令牌（绑定 _wf.tia_multi_block_pipeline）。
        # 仅非空占位串不足以通过（此前令牌从未被权威消费，确认机制形同虚设）。
        # mock 模式是测试骨架，按 core.py 既有约定跳过安全门。
        if isinstance(ctx._pool, McpConnectionPool):
            confirmation_token = ctx.input.get("confirmation_token", "")
            request_id = ctx.input.get("confirmation_request_id", "")
            if not isinstance(confirmation_token, str) or not confirmation_token.strip():
                from safety.confirmation_requests import _confirmation_request_store
                if isinstance(request_id, str) and request_id:
                    confirmation_token = _confirmation_request_store.take_token(request_id) or ""
                if not confirmation_token:
                    record = _confirmation_request_store.create(
                        "tia_multi_block_pipeline",
                        f"批量导入 {len(blocks)} 个 SCL 块",
                        operator="ai-agent",
                    )
                    raise ValueError(
                        "导入 SCL 到 TIA 工程属于工程态控制操作，需要人工批准。"
                        f"已创建人工审批请求 {record['request_id']}，请在审批界面批准后携带 confirmation_request_id 重试"
                    )
            try:
                from safety.confirmation import ConfirmationService, ConfirmationError
                ConfirmationService().consume(
                    confirmation_token,
                    operator="wf:tia_multi_block_pipeline",
                    target="_wf.tia_multi_block_pipeline",
                    value="run",
                    device_id="workflow",
                )
            except ConfirmationError as exc:
                raise ValueError(f"人工确认令牌无效: {exc}。由人工重新签发工作流确认令牌后重试") from exc

        # 按依赖顺序排序
        sorted_blocks = _sort_blocks_by_dependency(blocks)

        imported_names: list[str] = []
        step_index = 0

        # 逐个导入块
        for i, block in enumerate(sorted_blocks):
            step_index = i + 1
            block_type: str = block.get("type", "")
            block_name: str = block.get("name", "")
            scl_code: str = block.get("scl_code", "")

            # 块类型/块名约束/SCL 静态 lint 校验，任一不合规即 fail-closed 中止
            _validate_block_input(i, block)

            try:
                await ctx.call_async(
                    "tia-mcp.import_scl_file",
                    scl_code=scl_code,
                    block_name=block_name,
                    replace=True,
                )
                imported_names.append(block_name)
            except Exception as e:
                _logger.error(f"步骤 {step_index}: 导入块 {block_name} 失败: {e}")
                raise RuntimeError(f"导入块 {block_name!r} ({block_type}) 失败: {e}") from e

        # 全部导入完成后编译
        step_index = len(sorted_blocks) + 1
        try:
            compile_result = await ctx.call_async(
                "plc-mcp-bridge.plc_compile_project",
            )
        except Exception as e:
            _logger.error(f"步骤 {step_index}: 编译失败: {e}")
            raise RuntimeError(f"编译失败: {e}") from e

        compile_ok = compile_result.get("ok", compile_result.get("success", False))
        if not compile_ok:
            raise RuntimeError(f"编译失败: {compile_result.get('errors', '未知错误')}")

        return {
            "status": "ok",
            "total_blocks": len(sorted_blocks),
            "imported": imported_names,
            "compile_ok": True,
        }
