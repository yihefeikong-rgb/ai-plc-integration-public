#!/usr/bin/env python3
"""
安全互锁检查 — Phase 2 核心安全机制

规则:
  1. 写入前必须检查急停位和安全 OK 位
  2. 数值不能超出预设范围
  3. 连续 3 次异常自动熔断（禁止所有写入）
  4. 所有写入操作记录审计日志
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# ── 审计日志 ──
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

audit_logger = logging.getLogger("opcua_audit")
audit_logger.setLevel(logging.INFO)
_handler = logging.FileHandler(LOG_DIR / "opcua_audit.log", encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
audit_logger.addHandler(_handler)


# ── 互锁规则配置（硬编码默认值，后续从 YAML 加载）──
DEFAULT_INTERLOCKS = {
    "emergency_stop_node": "ns=3;s=DB1.EmergencyStop",
    "safety_ok_node": "ns=3;s=DB1.SafetyOK",
}

# ── 数值范围限制 ──
VALUE_LIMITS: dict[str, dict[str, Any]] = {
    "ns=3;s=DB1.MotorSpeed": {"min": 0, "max": 3000, "unit": "rpm"},
    "ns=3;s=DB1.HeaterPower": {"min": 0, "max": 100, "unit": "%"},
    "ns=3;s=DB1.ConveyorSpeed": {"min": 0, "max": 1500, "unit": "mm/s"},
    "ns=3;s=DB1.Pressure": {"min": 0, "max": 10, "unit": "bar"},
}

# ── 熔断器状态 ──
FUSE_STATE = {
    "tripped": False,
    "consecutive_errors": 0,
    "max_errors": 3,
    "trip_reason": "",
    "trip_time": None,
}


async def check_interlock(client) -> tuple[bool, str]:
    """检查互锁条件，返回 (允许写入, 原因)

    Args:
        client: asyncua Client 实例（已连接）

    Returns:
        (True, "OK") 允许写入
        (False, "原因") 禁止写入
    """
    # 熔断器检查
    if FUSE_STATE["tripped"]:
        return False, f"熔断器已触发: {FUSE_STATE['trip_reason']}（需要人工调用 reset_fuse 重置）"

    try:
        # 检查急停信号
        e_stop_node = client.get_node(DEFAULT_INTERLOCKS["emergency_stop_node"])
        e_stop_value = await e_stop_node.read_value()
        if e_stop_value:
            return False, "急停信号已触发(EmergencyStop=True)，禁止写入"

        # 检查安全 OK 位
        safety_node = client.get_node(DEFAULT_INTERLOCKS["safety_ok_node"])
        safety_value = await safety_node.read_value()
        if not safety_value:
            return False, "安全OK位未置位(SafetyOK=False)，禁止写入"

    except Exception as e:
        # 如果无法读取互锁节点，保守策略：禁止写入
        return False, f"无法读取互锁状态节点: {e}"

    return True, "OK"


async def check_interlock_lenient(client) -> tuple[bool, str]:
    """宽松互锁检查 — 互锁节点不存在时允许写入（适用于测试环境）

    Args:
        client: asyncua Client 实例

    Returns:
        (True, "OK") 或 (False, "原因")
    """
    if FUSE_STATE["tripped"]:
        return False, f"熔断器已触发: {FUSE_STATE['trip_reason']}（需要人工调用 reset_fuse 重置）"

    try:
        e_stop_node = client.get_node(DEFAULT_INTERLOCKS["emergency_stop_node"])
        e_stop_value = await e_stop_node.read_value()
        if e_stop_value:
            return False, "急停信号已触发(EmergencyStop=True)，禁止写入"
    except Exception:
        pass  # 节点不存在，跳过

    try:
        safety_node = client.get_node(DEFAULT_INTERLOCKS["safety_ok_node"])
        safety_value = await safety_node.read_value()
        if not safety_value:
            return False, "安全OK位未置位(SafetyOK=False)，禁止写入"
    except Exception:
        pass  # 节点不存在，跳过

    return True, "OK"


def check_value_range(node_id: str, value: Any) -> tuple[bool, str]:
    """检查值是否在允许范围内

    Args:
        node_id: OPC UA 节点 ID
        value: 要写入的值

    Returns:
        (True, "OK") 允许写入
        (False, "原因") 超出范围
    """
    if node_id not in VALUE_LIMITS:
        return True, "OK（无范围限制）"

    limits = VALUE_LIMITS[node_id]
    try:
        numeric_value = float(value)
    except (ValueError, TypeError):
        return True, "OK（非数值类型，跳过范围检查）"

    if numeric_value < limits["min"]:
        return False, f"值 {numeric_value} 低于最小值 {limits['min']} {limits['unit']}"
    if numeric_value > limits["max"]:
        return False, f"值 {numeric_value} 超出最大值 {limits['max']} {limits['unit']}"

    return True, "OK"


def record_write(node_id: str, value: Any, success: bool, reason: str = "") -> None:
    """记录写入审计日志

    Args:
        node_id: 节点 ID
        value: 写入的值
        success: 是否成功
        reason: 失败原因
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": "write",
        "node_id": node_id,
        "value": str(value),
        "success": success,
        "reason": reason,
    }
    audit_logger.info(json.dumps(entry, ensure_ascii=False))

    # 更新熔断器计数
    if not success:
        FUSE_STATE["consecutive_errors"] += 1
        if FUSE_STATE["consecutive_errors"] >= FUSE_STATE["max_errors"]:
            trip_fuse(f"连续 {FUSE_STATE['max_errors']} 次写入失败/异常")
    else:
        FUSE_STATE["consecutive_errors"] = 0


def trip_fuse(reason: str) -> None:
    """触发熔断 — 禁止所有后续写入"""
    FUSE_STATE["tripped"] = True
    FUSE_STATE["trip_reason"] = reason
    FUSE_STATE["trip_time"] = datetime.now().isoformat()
    audit_logger.warning(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "action": "FUSE_TRIPPED",
        "reason": reason,
    }, ensure_ascii=False))


def reset_fuse() -> str:
    """重置熔断器（需要人工确认后调用）

    Returns:
        重置结果消息
    """
    if not FUSE_STATE["tripped"]:
        return "熔断器未触发，无需重置"

    old_reason = FUSE_STATE["trip_reason"]
    FUSE_STATE["tripped"] = False
    FUSE_STATE["consecutive_errors"] = 0
    FUSE_STATE["trip_reason"] = ""
    FUSE_STATE["trip_time"] = None

    audit_logger.info(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "action": "FUSE_RESET",
        "previous_reason": old_reason,
    }, ensure_ascii=False))
    return f"熔断器已重置（之前触发原因: {old_reason}）"


def get_fuse_status() -> dict[str, Any]:
    """获取熔断器当前状态"""
    return {
        "tripped": FUSE_STATE["tripped"],
        "consecutive_errors": FUSE_STATE["consecutive_errors"],
        "max_errors": FUSE_STATE["max_errors"],
        "trip_reason": FUSE_STATE["trip_reason"],
        "trip_time": FUSE_STATE["trip_time"],
    }
