"""
机器人监控工作流 — robot_monitor。

读取机器人状态并生成结构化状态报告。
"""
from __future__ import annotations

import logging
from typing import Any

from orchestrator.core import WorkflowContext, OrchestratorEngine

_logger = logging.getLogger(__name__)


def register_robot_monitor_workflow(engine: OrchestratorEngine) -> None:
    """向编排引擎注册 robot_monitor 工作流"""

    @engine.workflow("robot_monitor")
    async def robot_monitor(ctx: WorkflowContext) -> dict[str, Any]:
        """机器人状态监控工作流

        步骤:
            1. get_status — 读取机器人完整状态
            2. 解析连接、急停、机械臂位置等字段
            3. 生成状态报告
        """
        # 步骤 1: 读取状态
        status = await ctx.call_async("robot-mcp.get_status")

        # 步骤 2: 解析关键字段
        connection = status.get("connection", "unknown")
        estop = status.get("emergency_stop", False)
        arm_position = status.get("estimated_position", "unknown")
        backend = status.get("backend", "none")
        plc_ip = status.get("plc_ip", "")
        scene = status.get("scene", "")
        sensors = status.get("sensors", {})

        # 步骤 3: 生成状态报告
        return {
            "connection": connection,
            "emergency_stop": estop,
            "arm_position": arm_position,
            "backend": backend,
            "plc_ip": plc_ip,
            "scene": scene,
            "sensors": sensors,
        }
