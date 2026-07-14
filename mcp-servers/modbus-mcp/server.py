"""
Modbus TCP MCP Server — OpenPLC 仿真 / 通用 Modbus 设备
阶段1：读线圈/寄存器  阶段2：写线圈/寄存器（带安全校验）
"""

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.append(str(_PROJECT_ROOT))

from fastmcp import FastMCP
from pymodbus.client import ModbusTcpClient
from mcp_common.config import env_config
from safety.validator import validator as safety_validator
from safety.shadow_simulator import shadow_sim
from safety.confirmation import ConfirmationError, ConfirmationService
from mcp_common.audit import authenticated_actor, get_audit_logger

audit = get_audit_logger()

settings = env_config()

mcp = FastMCP("modbus-plc")
_client: ModbusTcpClient | None = None

# ── 认证 ──
_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")
confirmation_service = ConfirmationService()


def _require_auth(token: str):
    """验证 auth token（必须设置 MCP_AUTH_TOKEN）"""
    if not _AUTH_TOKEN:
        raise PermissionError("MCP_AUTH_TOKEN 未配置，服务不可用")
    if token != _AUTH_TOKEN:
        raise PermissionError("认证失败：无效的 auth token")


def get_client() -> ModbusTcpClient:
    global _client
    if _client is None:
        _client = ModbusTcpClient(host=settings.modbus_host, port=settings.modbus_port)
        _client.connect()
    return _client


def _confirmation_device_id() -> str:
    return f"modbus:{settings.modbus_host}:{settings.modbus_port}:unit-1"


# ===== 阶段1：读取 =====

@mcp.tool()
async def read_coil(address: int, auth_token: str = "") -> dict:
    """读取线圈（%QX 输出）"""
    _require_auth(auth_token)
    try:
        c = get_client()
        rr = c.read_coils(address, count=1, device_id=1)
        val = rr.bits[0] if not rr.isError() else None
        audit.log("read", f"coil.{address}", str(val), success=not rr.isError())
        return {"address": address, "type": "coil", "value": val}
    except Exception as e:
        return {"address": address, "type": "coil", "error": str(e)}


@mcp.tool()
async def read_register(address: int, count: int = 1, auth_token: str = "") -> dict:
    """读取保持寄存器"""
    _require_auth(auth_token)
    try:
        c = get_client()
        rr = c.read_holding_registers(address, count=count, device_id=1)
        vals = rr.registers if not rr.isError() else None
        audit.log("read", f"reg.{address}", str(vals), success=not rr.isError())
        return {"address": address, "type": "register", "count": count, "values": vals}
    except Exception as e:
        return {"address": address, "type": "register", "error": str(e)}


@mcp.tool()
async def read_discrete_input(address: int, auth_token: str = "") -> dict:
    """读取离散输入（%IX 传感器）"""
    _require_auth(auth_token)
    try:
        c = get_client()
        rr = c.read_discrete_inputs(address, count=1, device_id=1)
        val = rr.bits[0] if not rr.isError() else None
        audit.log("read", f"input.{address}", str(val), success=not rr.isError())
        return {"address": address, "type": "discrete_input", "value": val}
    except Exception as e:
        return {"address": address, "type": "discrete_input", "error": str(e)}


# ===== 阶段2：写入（带安全校验）=====

@mcp.tool()
async def write_coil(
    address: int,
    value: bool,
    operator: str = "ai-agent",
    auth_token: str = "",
    confirmation_token: str = "",
) -> dict:
    """写入线圈（%QX 输出）"""
    _require_auth(auth_token)
    actor = authenticated_actor(auth_token, "modbus")
    tag = f"coil.{address}"
    result = safety_validator.validate(tag, value)
    if not result.allowed:
        audit.log("write_blocked", tag, str(value), operator=actor,
                  success=False, detail=result.reason)
        return {"address": address, "type": "coil", "status": "blocked", "reason": result.reason}
    if result.needs_confirmation:
        if not confirmation_token:
            reason = f"需要人工确认: {result.reason}"
            audit.log("write_blocked", tag, str(value), operator=actor,
                      success=False, detail=reason)
            return {"address": address, "type": "coil", "status": "blocked", "reason": reason}
        try:
            confirmation_service.consume(
                confirmation_token,
                operator=operator,
                target=tag,
                value=value,
                device_id=_confirmation_device_id(),
            )
        except ConfirmationError as exc:
            reason = str(exc)
            audit.log("write_blocked", tag, str(value), operator=actor,
                      success=False, detail=reason)
            return {"address": address, "type": "coil", "status": "blocked", "reason": reason}

    sim_result = await shadow_sim.simulate_write(tag, value)
    if not sim_result.safe:
        audit.log("shadow_rejected", tag, str(value), operator=actor,
                  success=False, detail=sim_result.reason)
        return {"address": address, "type": "coil", "status": "blocked", "reason": sim_result.reason}

    try:
        audit.begin_control_operation(
            "modbus.write_coil", tag, actor,
            {"address": address, "value": value, "unit_id": 1},
        )
        c = get_client()
        r = c.write_coil(address, value, device_id=1)
        ok = not r.isError()
        audit.log("write", tag, str(value), operator=actor, success=ok)
        return {"address": address, "type": "coil", "value": value, "status": "ok" if ok else "error"}
    except Exception as e:
        audit.log("write", tag, str(value), operator=actor, success=False, detail=str(e))
        safety_validator.consecutive_errors += 1
        return {"address": address, "type": "coil", "status": "error", "error": str(e)}


@mcp.tool()
async def write_register(
    address: int,
    value: int,
    operator: str = "ai-agent",
    auth_token: str = "",
    confirmation_token: str = "",
) -> dict:
    """写入保持寄存器"""
    _require_auth(auth_token)
    actor = authenticated_actor(auth_token, "modbus")
    tag = f"register.{address}"
    result = safety_validator.validate(tag, value)
    if not result.allowed:
        audit.log("write_blocked", tag, str(value), operator=actor,
                  success=False, detail=result.reason)
        return {"address": address, "type": "register", "status": "blocked", "reason": result.reason}
    if result.needs_confirmation:
        if not confirmation_token:
            reason = f"需要人工确认: {result.reason}"
            audit.log("write_blocked", tag, str(value), operator=actor,
                      success=False, detail=reason)
            return {"address": address, "type": "register", "status": "blocked", "reason": reason}
        try:
            confirmation_service.consume(
                confirmation_token,
                operator=operator,
                target=tag,
                value=value,
                device_id=_confirmation_device_id(),
            )
        except ConfirmationError as exc:
            reason = str(exc)
            audit.log("write_blocked", tag, str(value), operator=actor,
                      success=False, detail=reason)
            return {"address": address, "type": "register", "status": "blocked", "reason": reason}

    sim_result = await shadow_sim.simulate_write(tag, value)
    if not sim_result.safe:
        audit.log("shadow_rejected", tag, str(value), operator=actor,
                  success=False, detail=sim_result.reason)
        return {"address": address, "type": "register", "status": "blocked", "reason": sim_result.reason}

    try:
        audit.begin_control_operation(
            "modbus.write_register", tag, actor,
            {"address": address, "value": value, "unit_id": 1},
        )
        c = get_client()
        r = c.write_register(address, value, device_id=1)
        ok = not r.isError()
        audit.log("write", tag, str(value), operator=actor, success=ok)
        return {"address": address, "type": "register", "value": value, "status": "ok" if ok else "error"}
    except Exception as e:
        audit.log("write", tag, str(value), operator=actor, success=False, detail=str(e))
        safety_validator.consecutive_errors += 1
        return {"address": address, "type": "register", "status": "error", "error": str(e)}


@mcp.tool()
async def scan_devices(auth_token: str = "") -> list[dict]:
    """扫描 Modbus 网络设备"""
    _require_auth(auth_token)
    devices = []
    for slave_id in range(1, 11):
        try:
            c = get_client()
            rr = c.read_holding_registers(0, count=1, device_id=slave_id)
            if not rr.isError():
                devices.append({"slave_id": slave_id, "status": "online"})
        except Exception:
            pass
    return devices


if __name__ == "__main__":
    mcp.run()
