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
import os
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

_diag_logger = logging.getLogger("opcua_safety")


def _hmac_audit_log(action: str, target: str, value: str = "",
                    operator: str = "", success: bool = True, detail: str = "") -> None:
    """把关键安全事件写入 mcp_common.audit 的 HMAC 链式审计日志。

    本地 opcua_audit.log 只是明文副本，FUSE_TRIPPED 等关键事件必须同时
    进入 HMAC 审计链，否则可被篡改且不参与链校验。审计链不可用时降级为
    本地日志（熔断动作本身不能被审计链故障阻断）。
    """
    try:
        from mcp_common.audit import get_audit_logger

        get_audit_logger().log(
            action, target, value, operator=operator, success=success, detail=detail
        )
    except Exception as exc:
        audit_logger.warning(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "action": "HMAC_AUDIT_UNAVAILABLE",
            "reason": str(exc),
        }, ensure_ascii=False))


# ── 互锁规则配置（硬编码默认值，后续从 YAML 加载）──
# 节点名与 safety/interlock-rules.yml 的 require_bits 语义对齐：
# DB1.EmergencyStopOff / DB1.SafetyOK 均为"必须为 True 才允许写入"的安全位。
DEFAULT_INTERLOCKS = {
    "emergency_stop_node": "ns=3;s=DB1.EmergencyStopOff",
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
FUSE_STATE_FILE = LOG_DIR / "opcua_fuse_state.json"
FUSE_STATE = {
    "tripped": False,
    "consecutive_errors": 0,
    "max_errors": 3,
    "trip_reason": "",
    "trip_time": None,
}


def _load_fuse_state() -> None:
    """从磁盘恢复熔断器状态，防止进程重启绕过熔断。

    文件不存在是正常的首次启动（未熔断）；文件存在但损坏/不可读时
    按已熔断处理（fail-closed）：无法核实的历史熔断状态不能当作
    "未熔断"放行写入，必须人工调用 reset_fuse 才能恢复。
    """
    if not FUSE_STATE_FILE.exists():
        return
    try:
        data = json.loads(FUSE_STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("熔断状态不是 JSON 对象")
        FUSE_STATE["tripped"] = bool(data.get("tripped", False))
        FUSE_STATE["consecutive_errors"] = int(data.get("consecutive_errors", 0))
        FUSE_STATE["max_errors"] = int(data.get("max_errors", FUSE_STATE["max_errors"]))
        FUSE_STATE["trip_reason"] = str(data.get("trip_reason", ""))
        FUSE_STATE["trip_time"] = data.get("trip_time")
    except Exception as exc:
        # 状态文件存在但损坏/不可读：按已熔断处理并记录 error 日志
        _diag_logger.error("熔断状态文件损坏，按已熔断处理（fail-closed）: %s", exc)
        audit_logger.warning(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "action": "FUSE_STATE_CORRUPTED_FAIL_CLOSED",
            "reason": str(exc),
        }, ensure_ascii=False))
        FUSE_STATE["tripped"] = True
        FUSE_STATE["trip_reason"] = "熔断状态文件损坏，按已熔断处理（fail-closed，需人工 reset_fuse）"
        FUSE_STATE["trip_time"] = datetime.now().isoformat()


def _save_fuse_state() -> None:
    """持久化熔断器状态（临时文件 + os.replace 原子写）。

    直接覆盖原文件会在写入中途崩溃/断电时留下半写的损坏状态文件，
    触发 fail-closed 误熔断；原子替换保证状态文件要么是旧完整内容、
    要么是新完整内容。
    """
    tmp_path = FUSE_STATE_FILE.with_name(FUSE_STATE_FILE.name + ".tmp")
    try:
        tmp_path.write_text(
            json.dumps(FUSE_STATE, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp_path, FUSE_STATE_FILE)
    except Exception as exc:
        _diag_logger.error("熔断状态持久化失败: %s", exc)
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


_load_fuse_state()


def _bit_is_set(value: Any) -> bool:
    """判断互锁安全位是否为"置位/安全"。

    只有明确为真值（True/1/"1"/"true" 等）才算安全，其余情况
    （None、0、"0"、"false"、未知类型、读取失败占位值）一律视为未置位，
    保证 fail-closed。
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on", "ok")
    if isinstance(value, (int, float)):
        return value != 0
    return False


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
        # 批量读取急停确认位与安全 OK 位（单次 UA 往返，避免两次串行读）
        e_stop_node = client.get_node(DEFAULT_INTERLOCKS["emergency_stop_node"])
        safety_node = client.get_node(DEFAULT_INTERLOCKS["safety_ok_node"])
        e_stop_value, safety_value = await client.read_values([e_stop_node, safety_node])

        # 急停确认位必须为 True（EmergencyStopOff=True 表示急停未触发）
        if not _bit_is_set(e_stop_value):
            return False, "急停确认位未置位(EmergencyStopOff=False)，禁止写入"

        # 安全 OK 位必须为 True
        if not _bit_is_set(safety_value):
            return False, "安全OK位未置位(SafetyOK=False)，禁止写入"

    except Exception as exc:
        # 无法确认互锁状态时保守策略：禁止写入（fail-closed）。
        # 异常细节只进服务端诊断日志，不进入审计日志或客户端消息。
        _diag_logger.warning("读取互锁状态节点失败: %s", exc)
        return False, "无法读取互锁状态节点，禁止写入"

    return True, "OK"


async def check_interlock_lenient(client) -> tuple[bool, str]:
    """互锁检查（fail-closed）。

    历史宽松版本在互锁节点读取失败时 except: pass 放行写入，构成急停
    旁路，已移除。本函数保留公开 API 兼容性，行为与 check_interlock
    完全一致（fail-closed）。当前仓库无调用方，后续可整体删除。
    """
    return await check_interlock(client)


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
        # 数值受限节点收到非数值输入时 fail-closed，不允许绕过范围检查
        return False, f"节点 {node_id} 要求数值类型，值 {value} 无法转换为数值，拒绝写入"

    if numeric_value < limits["min"]:
        return False, f"值 {numeric_value} 低于最小值 {limits['min']} {limits['unit']}"
    if numeric_value > limits["max"]:
        return False, f"值 {numeric_value} 超出最大值 {limits['max']} {limits['unit']}"

    return True, "OK"


def record_write(node_id: str, value: Any, success: bool, reason: str = "",
                 *, operator: str = "", count_fuse: bool = True) -> None:
    """记录写入审计日志

    Args:
        node_id: 节点 ID
        value: 写入的值
        success: 是否成功
        reason: 失败原因
        operator: 操作者身份（审计主体，不记录原始令牌）
        count_fuse: 是否计入熔断连续错误计数。互锁/范围等正常保护性拒绝
            不应触发熔断，调用方应传 False；仅真实写入失败传 True。
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": "write",
        "node_id": node_id,
        "value": str(value),
        "success": success,
        "reason": reason,
    }
    if operator:
        entry["operator"] = operator
    audit_logger.info(json.dumps(entry, ensure_ascii=False))

    # 更新熔断器计数：只统计真实写入失败；保护性拒绝不计；
    # 已熔断后不再累加，避免连续错误计数无限增长。
    if not success and count_fuse and not FUSE_STATE["tripped"]:
        FUSE_STATE["consecutive_errors"] += 1
        if FUSE_STATE["consecutive_errors"] >= FUSE_STATE["max_errors"]:
            trip_fuse(f"连续 {FUSE_STATE['max_errors']} 次写入失败/异常", operator=operator)
        else:
            _save_fuse_state()
    elif success and FUSE_STATE["consecutive_errors"]:
        FUSE_STATE["consecutive_errors"] = 0
        _save_fuse_state()


def trip_fuse(reason: str, *, operator: str = "") -> None:
    """触发熔断 — 禁止所有后续写入"""
    FUSE_STATE["tripped"] = True
    FUSE_STATE["trip_reason"] = reason
    FUSE_STATE["trip_time"] = datetime.now().isoformat()
    _save_fuse_state()
    event = {
        "timestamp": datetime.now().isoformat(),
        "action": "FUSE_TRIPPED",
        "reason": reason,
    }
    if operator:
        event["operator"] = operator
    audit_logger.warning(json.dumps(event, ensure_ascii=False))
    # 关键安全事件必须进入 HMAC 审计链，不能只落在本地明文日志
    _hmac_audit_log("fuse_tripped", "opcua.fuse", reason,
                    operator=operator, success=False, detail=reason)


def reset_fuse(*, operator: str = "") -> str:
    """重置熔断器（需要人工确认后调用）

    Args:
        operator: 操作者身份（审计主体，不记录原始令牌）

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
    _save_fuse_state()

    event = {
        "timestamp": datetime.now().isoformat(),
        "action": "FUSE_RESET",
        "previous_reason": old_reason,
    }
    if operator:
        event["operator"] = operator
    audit_logger.info(json.dumps(event, ensure_ascii=False))
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
