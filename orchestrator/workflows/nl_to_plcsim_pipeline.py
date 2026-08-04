"""自然语言到 PLCSIM Advanced 的第一版主链工作流。"""
from __future__ import annotations

from typing import Any

from orchestrator.core import OrchestratorEngine, WorkflowContext
from orchestrator.mcp_pool import McpConnectionPool

DEFAULT_ACCEPTANCE_PROMPT = "三相异步电机正反转带急停和过载保护"
_ALLOWED_INPUT_FIELDS = {"description", "block_name", "launch_fio", "dry_run",
                         "confirmation_token", "confirmation_request_id"}


def _is_ok(result: Any) -> bool:
    if isinstance(result, dict):
        if result.get("error") not in (None, "", False, 0, [], {}):
            return False
        if result.get("ok") is False or result.get("success") is False:
            return False
        if str(result.get("status", "")).lower() in {"error", "failed", "fail"}:
            return False
        if "text" in result:
            return _is_ok(result["text"])
        return bool(result)
    text = str(result).strip()
    if not text:
        return False
    # 与 mcp_client._from_text / core._unwrap_tool_result 保持一致：
    # 失败信号只在文本开头生效，"编译成功，0 错误"这类诊断文本不能被误判为失败。
    if text.startswith(("!", "❌", "🚫", "失败", "错误", "被拒绝")):
        return False
    return any(marker in text for marker in ("✅", "成功", "已连接", "已断开", "📍"))


def _is_dry_run_preview(result: Any) -> bool:
    """识别 MCP 工具返回的 dry-run 预览（🔍/Dry-Run 标记，既非成功也非失败）。"""
    if isinstance(result, dict):
        text = result.get("text", "")
        return isinstance(text, str) and _is_dry_run_preview(text)
    return "🔍" in str(result) or "Dry-Run" in str(result)


def _fail(message: str, suggestion: str) -> None:
    raise RuntimeError(f"{message}。下一步: {suggestion}")


def _block_name_from(result: Any, fallback: str) -> str:
    if isinstance(result, dict):
        return result.get("blockName") or result.get("block_name") or fallback
    return fallback


def register_nl_to_plcsim_pipeline_workflow(engine: OrchestratorEngine) -> None:
    """注册 `nl_to_plcsim_pipeline` 工作流。"""

    @engine.workflow("nl_to_plcsim_pipeline")
    async def nl_to_plcsim_pipeline(ctx: WorkflowContext) -> dict[str, Any]:
        unsupported = sorted(set(ctx.input) - _ALLOWED_INPUT_FIELDS)
        if unsupported:
            _fail(
                f"不支持的工作流参数: {', '.join(unsupported)}",
                "删除目标 IP 或工程路径覆盖，使用受控配置后重试",
            )

        description = (ctx.input.get("description") or DEFAULT_ACCEPTANCE_PROMPT).strip()
        if not description:
            _fail("缺少自然语言需求描述", "填写 description 后重试")

        block_name = ctx.input.get("block_name", "AutoGen")
        launch_fio = bool(ctx.input.get("launch_fio", False))
        dry_run = bool(ctx.input.get("dry_run", False))
        confirmation_token = ctx.input.get("confirmation_token", "")

        # 生产链路（真实 MCP 连接池）下，编译→下载→连接→FIO 是危险操作链，
        # 必须由人工确认令牌真实授权才能执行：编排层在入口消费一次性工作流级
        # 确认令牌（绑定 _wf.nl_to_plcsim_pipeline）。令牌必须真实有效——
        # 仅非空占位串不足以通过（此前仅存在性检查，确认机制形同虚设）。
        # dry_run 预览不产生任何副作用，无需确认令牌。
        if not dry_run and isinstance(ctx._pool, McpConnectionPool):
            request_id = ctx.input.get("confirmation_request_id", "")
            if not isinstance(confirmation_token, str) or not confirmation_token.strip():
                from safety.confirmation_requests import _confirmation_request_store
                if isinstance(request_id, str) and request_id:
                    # 凭 request_id 领取人工已批准的一次性令牌
                    confirmation_token = _confirmation_request_store.take_token(request_id) or ""
                if not confirmation_token:
                    # 未批准/无令牌：创建人工审批请求并返回 request_id
                    record = _confirmation_request_store.create(
                        "nl_to_plcsim_pipeline",
                        f"自然语言需求: {description[:120]}",
                        operator="ai-agent",
                    )
                    raise RuntimeError(
                        f"危险操作链需要人工批准。已创建人工审批请求 {record['request_id']}，"
                        "请在审批界面批准后，携带 confirmation_request_id 重新执行本工作流"
                    )
            try:
                from safety.confirmation import ConfirmationService, ConfirmationError
                ConfirmationService().consume(
                    confirmation_token,
                    operator="wf:nl_to_plcsim_pipeline",
                    target="_wf.nl_to_plcsim_pipeline",
                    value="run",
                    device_id="workflow",
                )
            except ConfirmationError as exc:
                _fail(
                    f"人工确认令牌无效: {exc}",
                    "由人工重新签发工作流确认令牌后重试（令牌一次性有效，且须在有效期内）",
                )

        if dry_run:
            preview = await ctx.call_async(
                "plc-mcp-bridge.plc_download_project",
                method="auto",
                compile_first=False,
                dry_run=True,
            )
            if not _is_ok(preview) and not _is_dry_run_preview(preview):
                _fail("下载预览失败", "确认 TIA Portal、PLCSIM Advanced 和虚拟网卡均已就绪")
            return {
                "status": "ok",
                "dry_run": True,
                "description": description,
                "block_name": block_name,
                "snap7_verified": False,
                "fio_requested": False,
            }

        ladder = await ctx.call_async(
            "tia-mcp.create_ladder_block",
            description=description,
            block_name=block_name,
        )
        if not _is_ok(ladder):
            _fail("生成或导入 LAD 梯形图块失败", "检查 DeepSeek Key、CartGen 输出和 TIA 项目路径")

        generated_block = _block_name_from(ladder, block_name)
        ob1 = await ctx.call_async(
            "tia-mcp.call_fb_in_ob1",
            fb_names=[generated_block],
        )
        if not _is_ok(ob1):
            _fail("OB1 调用链创建失败", "检查生成块是否已导入 TIA 项目")

        compile_result = await ctx.call_async("plc-mcp-bridge.plc_compile_project")
        if not _is_ok(compile_result):
            _fail("编译失败", "检查 TIA 编译错误并修正生成块或 IO 映射")

        download = await ctx.call_async(
            "plc-mcp-bridge.plc_download_project",
            method="auto",
            compile_first=False,
        )
        if not _is_ok(download):
            _fail("下载到 PLCSIM 失败", "确认 TIA Portal、PLCSIM Advanced 和虚拟网卡均已就绪")

        connected = await ctx.call_async("plc-mcp-bridge.s7_connect")
        if not _is_ok(connected):
            _fail("snap7 连接 PLCSIM 失败", "确认 PLCSIM 实例 factoryio 已启动且 IP 匹配")

        readback = await ctx.call_async("plc-mcp-bridge.s7_read", address="M0.0")
        if not _is_ok(readback):
            _fail("snap7 回读失败", "确认程序已下载且 CPU 处于 RUN")

        await ctx.call_async("plc-mcp-bridge.s7_disconnect")

        if launch_fio:
            fio_cfg = await ctx.call_async(
                "plc-mcp-bridge.plc_fio_write_config",
                instance_name="factoryio",
            )
            if not _is_ok(fio_cfg):
                _fail("Factory I/O 配置写入失败", "确认 auto.cfg 写入权限")
            fio_launch = await ctx.call_async("plc-mcp-bridge.plc_fio_launch")
            if not _is_ok(fio_launch):
                _fail("Factory I/O 启动失败", "确认 Factory IO.exe 路径配置正确")

        return {
            "status": "ok",
            "description": description,
            "block_name": generated_block,
            "snap7_verified": True,
            "fio_requested": launch_fio,
        }
