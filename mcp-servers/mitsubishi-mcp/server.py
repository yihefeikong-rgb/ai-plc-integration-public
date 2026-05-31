"""
三菱 MC 协议 MCP Server — 阶段1：读 + 阶段2：写
支持 FX3U / FX5U，TCP Binary 模式
"""

import asyncio
from fastmcp import FastMCP
from config.settings import settings
from safety.validator import validator as safety_validator
from safety.audit import audit
from .mc_protocol import (
    build_read_request, build_write_request,
    parse_read_response, parse_write_response, MCFrameError,
)

mcp = FastMCP("mitsubishi-plc")
_reader: asyncio.StreamReader | None = None
_writer: asyncio.StreamWriter | None = None


async def get_connection():
    global _reader, _writer
    if _reader is None:
        _reader, _writer = await asyncio.open_connection(
            settings.melsec_host, settings.melsec_port
        )
    return _reader, _writer


# ===== 阶段1：读取 =====

@mcp.tool()
async def read_device(addr: str) -> dict:
    """读取单个设备地址（如 'M100', 'D200'）"""
    try:
        r, w = await get_connection()
        frame = build_read_request(addr, 1)
        w.write(frame)
        await w.drain()
        resp = await asyncio.wait_for(r.read(1024), timeout=5.0)
        values = parse_read_response(resp, addr)
        audit.log("read", addr, str(values[0]), success=True)
        return {"device": addr, "value": values[0], "status": "ok"}
    except Exception as e:
        audit.log("read", addr, success=False, detail=str(e))
        return {"device": addr, "error": str(e), "status": "error"}


@mcp.tool()
async def read_devices(addresses: list[str]) -> list[dict]:
    """批量读取设备"""
    return [await read_device(a) for a in addresses]


# ===== 阶段2：写入（带安全校验）=====

@mcp.tool()
async def write_device(addr: str, value: int, operator: str = "ai-agent") -> dict:
    """写入设备地址"""
    result = safety_validator.validate(addr, value)
    if not result.allowed:
        audit.log("write_blocked", addr, str(value), operator=operator,
                  success=False, detail=result.reason)
        return {"device": addr, "status": "blocked", "reason": result.reason}

    try:
        r, w = await get_connection()
        frame = build_write_request(addr, value)
        w.write(frame)
        await w.drain()
        resp = await asyncio.wait_for(r.read(1024), timeout=5.0)
        parse_write_response(resp)
        audit.log("write", addr, str(value), operator=operator, success=True)
        return {"device": addr, "value": value, "status": "ok",
                "needs_confirmation": result.needs_confirmation}
    except Exception as e:
        audit.log("write", addr, str(value), operator=operator,
                  success=False, detail=str(e))
        safety_validator.record_error()
        return {"device": addr, "status": "error", "error": str(e)}


if __name__ == "__main__":
    mcp.run()
