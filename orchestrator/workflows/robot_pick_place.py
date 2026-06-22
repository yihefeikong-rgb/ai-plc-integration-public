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
            2. 急停检查 — 如果 estop 激活则中止
            3. go_home — 回位
            4. control_conveyor(entry) — 启动入口传送带
            5. pick_item — 拾取物料
            6. control_conveyor(exit) — 启动出口传送带
            7. place_item — 放置物料
        """
        # 步骤 1: 检查机器人状态
        status = await ctx.call_async("robot-mcp.get_status")

        # 步骤 2: 急停检查
        estop = status.get("emergency_stop", False)
        if estop:
            return {
                "status": "error",
                "error": "急停已触发，工作流中止",
                "emergency_stop": True,
            }

        # 步骤 3: 回位
        await ctx.call_async("robot-mcp.go_home")

        # 步骤 4: 启动入口传送带
        await ctx.call_async("robot-mcp.control_conveyor", direction="entry")

        # 步骤 5: 拾取
        pick_result = await ctx.call_async("robot-mcp.pick_item")

        # 步骤 6: 启动出口传送带
        await ctx.call_async("robot-mcp.control_conveyor", direction="exit")

        # 步骤 7: 放置
        place_result = await ctx.call_async("robot-mcp.place_item")

        return {
            "status": "ok",
            "pick": pick_result,
            "place": place_result,
        }
