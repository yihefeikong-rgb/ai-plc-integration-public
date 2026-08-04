"""
机器人拾取-放置工作流 — robot_pick_place。

通过编排层执行完整的 pick-and-place 流程：
  检查状态 → 急停校验 → 回位 → 入口传送带 → 拾取 → 出口传送带 → 放置
"""
from __future__ import annotations

import logging
from typing import Any

from orchestrator.core import WorkflowContext, OrchestratorEngine

_logger = logging.getLogger(__name__)


def register_robot_pick_place_workflow(engine: OrchestratorEngine) -> None:
    """向编排引擎注册 robot_pick_place 工作流"""

    @engine.workflow("robot_pick_place")
    async def robot_pick_place(ctx: WorkflowContext) -> dict[str, Any]:
        """机器人拾取-放置工作流

        步骤:
            1. get_status — 检查机器人状态
            2. go_home — 回位
            3. control_conveyor(entry) — 启动入口传送带
            4. pick_item — 拾取物料
            5. control_conveyor(exit) — 启动出口传送带
            6. place_item — 放置物料

        安全约束:
            - 急停检查 fail-closed：字段缺失/未知视为急停激活，中止流程
            - 每个物理动作前重新读取状态，动作序列之间复检急停
        """
        async def _check_estop() -> dict[str, Any] | None:
            """重新读取机器人状态并执行 fail-closed 急停检查。

            急停字段缺失或状态未知时按急停激活处理（fail-closed），
            返回急停错误响应字典；确认未急停时返回 None。
            """
            status = await ctx.call_async("robot-mcp.get_status")
            estop_value = status.get("emergency_stop")
            if estop_value is None:
                # 急停字段缺失/未知：fail-closed，不得继续执行物理动作
                return {
                    "status": "error",
                    "error": "无法确认急停状态，工作流中止",
                    "emergency_stop": "unknown",
                }
            if estop_value:
                return {
                    "status": "error",
                    "error": "急停已触发，工作流中止",
                    "emergency_stop": True,
                }
            return None

        # 步骤 1: 首次急停检查（fail-closed）
        estop_error = await _check_estop()
        if estop_error is not None:
            return estop_error

        # 步骤 2: 回位（动作前复检急停）
        await ctx.call_async("robot-mcp.go_home")
        estop_error = await _check_estop()
        if estop_error is not None:
            return estop_error

        # 步骤 3: 启动入口传送带（动作前复检急停）
        await ctx.call_async("robot-mcp.control_conveyor", direction="entry")
        estop_error = await _check_estop()
        if estop_error is not None:
            return estop_error

        # 步骤 4: 拾取（动作前复检急停）
        pick_result = await ctx.call_async("robot-mcp.pick_item")
        estop_error = await _check_estop()
        if estop_error is not None:
            return estop_error

        # 步骤 5: 启动出口传送带（动作前复检急停）
        await ctx.call_async("robot-mcp.control_conveyor", direction="exit")
        estop_error = await _check_estop()
        if estop_error is not None:
            return estop_error

        # 步骤 6: 放置
        place_result = await ctx.call_async("robot-mcp.place_item")

        return {
            "status": "ok",
            "pick": pick_result,
            "place": place_result,
        }
