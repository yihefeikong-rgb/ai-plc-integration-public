"""
Modbus TCP MCP Server — OpenPLC 仿真 / 通用 Modbus 设备
阶段1：读线圈/寄存器  阶段2：写线圈/寄存器（带安全校验）
"""

from fastmcp import FastMCP
from pymodbus.client import ModbusTcpClient
from config.settings import settings
from safety.validator import validator as safety_validator
from safety.audit import audit

mcp = FastMCP("modbus-plc")
_client: ModbusTcpClient | None = None


def get_client() -> ModbusTcpClient:
    global _client
    if _client is None:
        _client = ModbusTcpClient(host=settings.modbus_host, port=settings.modbus_port)
        _client.connect()
    return _client


# ===== 阶段1：读取 =====

@mcp.tool()
async def read_coil(address: int) -> dict:
    """读取线圈（%QX 输出）"""
    try:
        c = get_client()
        rr = c.read_coils(address, count=1, device_id=1)
        val = rr.bits[0] if not rr.isError() else None
        audit.log("read", f"coil.{address}", str(val), success=not rr.isError())
        return {"address": address, "type": "coil", "value": val}
    except Exception as e:
        return {"address": address, "type": "coil", "error": str(e)}


@mcp.tool()
async def read_register(address: int, count: int = 1) -> dict:
    """读取保持寄存器"""
    try:
        c = get_client()
        rr = c.read_holding_registers(address, count=count, device_id=1)
        vals = rr.registers if not rr.isError() else None
        audit.log("read", f"reg.{address}", str(vals), success=not rr.isError())
        return {"address": address, "type": "register", "count": count, "values": vals}
    except Exception as e:
        return {"address": address, "type": "register", "error": str(e)}


@mcp.tool()
async def read_discrete_input(address: int) -> dict:
    """读取离散输入（%IX 传感器）"""
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
async def write_coil(address: int, value: bool, operator: str = "ai-agent") -> dict:
    """写入线圈（%QX 输出）"""
    tag = f"coil.{address}"
    result = safety_validator.validate(tag, value)
    if not result.allowed:
        audit.log("write_blocked", tag, str(value), operator=operator,
                  success=False, detail=result.reason)
        return {"address": address, "type": "coil", "status": "blocked", "reason": result.reason}

    try:
        c = get_client()
        r = c.write_coil(address, value, device_id=1)
        ok = not r.isError()
        audit.log("write", tag, str(value), operator=operator, success=ok)
        return {"address": address, "type": "coil", "value": value, "status": "ok" if ok else "error"}
    except Exception as e:
        audit.log("write", tag, str(value), operator=operator, success=False, detail=str(e))
        safety_validator.record_error()
        return {"address": address, "type": "coil", "status": "error", "error": str(e)}


@mcp.tool()
async def write_register(address: int, value: int, operator: str = "ai-agent") -> dict:
    """写入保持寄存器"""
    tag = f"register.{address}"
    result = safety_validator.validate(tag, value)
    if not result.allowed:
        audit.log("write_blocked", tag, str(value), operator=operator,
                  success=False, detail=result.reason)
        return {"address": address, "type": "register", "status": "blocked", "reason": result.reason}

    try:
        c = get_client()
        r = c.write_register(address, value, device_id=1)
        ok = not r.isError()
        audit.log("write", tag, str(value), operator=operator, success=ok)
        return {"address": address, "type": "register", "value": value, "status": "ok" if ok else "error"}
    except Exception as e:
        audit.log("write", tag, str(value), operator=operator, success=False, detail=str(e))
        safety_validator.record_error()
        return {"address": address, "type": "register", "status": "error", "error": str(e)}


@mcp.tool()
async def scan_devices() -> list[dict]:
    """扫描 Modbus 网络设备"""
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
