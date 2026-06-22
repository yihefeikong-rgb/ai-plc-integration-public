"""
S7 监控工作流 — 读取 PLC 标签值、检测变化、AI 分析、安全写入。

演示编排层的读取-分析-写入闭环：
- 读取当前值（s7_read）
- 变化检测（纯函数）
- AI 分析（mock）
- 安全写入（s7_write，自动经过 SafetyGate）
"""
from __future__ import annotations

import logging
from typing import Any

from orchestrator.core import WorkflowContext, OrchestratorEngine

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def detect_change(current: float, previous: float, threshold: float) -> bool:
    """检测当前值与上次值的变化是否超过阈值。

    Args:
        current: 当前读取值
        previous: 上次值（或目标值）
        threshold: 变化阈值

    Returns:
        True 表示变化显著，需要关注
    """
    return abs(current - previous) > threshold


def mock_ai_analyze(tag: str, current_value: float, delta: float) -> dict[str, Any]:
    """Mock AI 分析 — 根据当前值和变化量生成控制建议。

    Args:
        tag: PLC 标签名
        current_value: 当前值
        delta: 与上次值的差值

    Returns:
        {"action": "write"|"hold", "value": float, "reason": str}
    """
    if abs(delta) < 0.5:
        return {
            "action": "hold",
            "value": current_value,
            "reason": f"标签 {tag} 变化量 {delta:.2f} 较小，建议保持当前值",
        }

    # 模拟一个简单的回退控制：如果值偏高就下调，偏低就上调
    target = 100.0  # 假设设定点为 100
    if current_value > target + 5:
        new_value = target
        return {
            "action": "write",
            "value": new_value,
            "reason": f"标签 {tag} 当前值 {current_value:.2f} 偏高，建议回调至 {new_value}",
        }
    elif current_value < target - 5:
        new_value = target
        return {
            "action": "write",
            "value": new_value,
            "reason": f"标签 {tag} 当前值 {current_value:.2f} 偏低，建议上调至 {new_value}",
        }

    return {
        "action": "hold",
        "value": current_value,
        "reason": f"标签 {tag} 当前值 {current_value:.2f} 在正常范围内",
    }


# ---------------------------------------------------------------------------
# 工作流注册
# ---------------------------------------------------------------------------

def register_s7_monitor_workflow(engine: OrchestratorEngine) -> None:
    """向编排引擎注册 s7_monitor 工作流"""

    @engine.workflow("s7_monitor")
    async def s7_monitor(ctx: WorkflowContext) -> dict[str, Any]:
        """S7 标签监控：读取 → 变化检测 → AI 分析 → 安全写入

        步骤:
            1. read_current_value — 读取 PLC 标签当前值
            2. detect_change — 比较当前值与上次值/目标值
            3. ai_analyze — 如果变化显著，生成控制建议
            4. safe_write — 如果有写入建议，执行安全写入

        ctx.input 参数:
            tag_name: PLC 标签名（必填）
            target_value: 目标值/上次值（可选，默认使用当前值）
            delta_threshold: 变化阈值（可选，默认 0.1）
        """
        tag_name: str = ctx.input["tag_name"]
        target_value: float | None = ctx.input.get("target_value")
        delta_threshold: float = ctx.input.get("delta_threshold", 0.1)

        # 步骤 1: 读取当前值
        read_result = await ctx.call_async(
            "plc-mcp-bridge.s7_read", tag=tag_name
        )
        current_value: float = float(read_result.get("value", 0))

        # 步骤 2: 变化检测
        reference = target_value if target_value is not None else current_value
        delta = current_value - reference
        changed = detect_change(current_value, reference, delta_threshold)

        # 步骤 3: AI 分析（如果变化显著）
        ai_result: dict[str, Any] | None = None
        if changed:
            ai_result = mock_ai_analyze(tag_name, current_value, delta)

        # 步骤 4: 安全写入（如果 AI 建议写入）
        write_result: dict[str, Any] | None = None
        if ai_result and ai_result["action"] == "write":
            write_result = await ctx.call_async(
                "plc-mcp-bridge.s7_write",
                tag=tag_name,
                value=ai_result["value"],
            )

        return {
            "tag_name": tag_name,
            "current_value": current_value,
            "delta": delta,
            "changed": changed,
            "ai_recommendation": ai_result,
            "write_result": write_result,
        }
