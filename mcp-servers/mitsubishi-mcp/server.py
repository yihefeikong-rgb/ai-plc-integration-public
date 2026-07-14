"""
三菱 MC 协议 MCP Server — 阶段1：读 + 阶段2：写
支持 FX3U / FX5U，TCP Binary 模式
"""

import os
import sys
import asyncio
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_MODULE_DIR = Path(__file__).parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.append(str(_PROJECT_ROOT))
if str(_MODULE_DIR) not in sys.path:
    sys.path.append(str(_MODULE_DIR))

from fastmcp import FastMCP
from mcp_common.config import env_config
from safety.validator import validator as safety_validator
from safety.shadow_simulator import shadow_sim
from safety.confirmation import ConfirmationError, ConfirmationService
from mcp_common.audit import authenticated_actor, get_audit_logger

audit = get_audit_logger()
from mc_protocol import (
    build_read_request, build_write_request,
    parse_read_response, parse_write_response, MCFrameError,
)

settings = env_config()

mcp = FastMCP("mitsubishi-plc")
_reader: asyncio.StreamReader | None = None
_writer: asyncio.StreamWriter | None = None

# ── 认证 ──
_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")
confirmation_service = ConfirmationService()


def _require_auth(token: str):
    """验证 auth token（必须设置 MCP_AUTH_TOKEN）"""
    if not _AUTH_TOKEN:
        raise PermissionError("MCP_AUTH_TOKEN 未配置，服务不可用")
    if token != _AUTH_TOKEN:
        raise PermissionError("认证失败：无效的 auth token")


async def get_connection():
    global _reader, _writer
    if _reader is None:
        _reader, _writer = await asyncio.open_connection(
            settings.melsec_host, settings.melsec_port
        )
    return _reader, _writer


def _confirmation_device_id() -> str:
    return f"melsec:{settings.melsec_host}:{settings.melsec_port}"


# ===== 阶段1：读取 =====

@mcp.tool()
async def read_device(addr: str, auth_token: str = "") -> dict:
    """读取单个设备地址（如 'M100', 'D200'）"""
    _require_auth(auth_token)
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
async def read_devices(addresses: list[str], auth_token: str = "") -> list[dict]:
    """批量读取设备"""
    _require_auth(auth_token)
    return [await read_device(a, auth_token=auth_token) for a in addresses]


# ===== 阶段2：写入（带安全校验）=====

@mcp.tool()
async def write_device(
    addr: str,
    value: int,
    operator: str = "ai-agent",
    auth_token: str = "",
    confirmation_token: str = "",
) -> dict:
    """写入设备地址"""
    _require_auth(auth_token)
    actor = authenticated_actor(auth_token, "melsec")
    result = safety_validator.validate(addr, value)
    if not result.allowed:
        audit.log("write_blocked", addr, str(value), operator=actor,
                  success=False, detail=result.reason)
        return {"device": addr, "status": "blocked", "reason": result.reason}
    if result.needs_confirmation:
        if not confirmation_token:
            reason = f"需要人工确认: {result.reason}"
            audit.log("write_blocked", addr, str(value), operator=actor,
                      success=False, detail=reason)
            return {"device": addr, "status": "blocked", "reason": reason}
        try:
            confirmation_service.consume(
                confirmation_token,
                operator=operator,
                target=addr,
                value=value,
                device_id=_confirmation_device_id(),
            )
        except ConfirmationError as exc:
            reason = str(exc)
            audit.log("write_blocked", addr, str(value), operator=actor,
                      success=False, detail=reason)
            return {"device": addr, "status": "blocked", "reason": reason}

    sim_result = await shadow_sim.simulate_write(addr, value)
    if not sim_result.safe:
        audit.log("shadow_rejected", addr, str(value), operator=actor,
                  success=False, detail=sim_result.reason)
        return {"device": addr, "status": "blocked", "reason": sim_result.reason}

    try:
        audit.begin_control_operation(
            "melsec.write_device", addr, actor,
            {"address": addr, "value": value},
        )
        r, w = await get_connection()
        frame = build_write_request(addr, value)
        w.write(frame)
        await w.drain()
        resp = await asyncio.wait_for(r.read(1024), timeout=5.0)
        parse_write_response(resp)
        audit.log("write", addr, str(value), operator=actor, success=True)
        return {"device": addr, "value": value, "status": "ok",
                "needs_confirmation": result.needs_confirmation}
    except Exception as e:
        audit.log("write", addr, str(value), operator=actor,
                  success=False, detail=str(e))
        safety_validator.consecutive_errors += 1
        return {"device": addr, "status": "error", "error": str(e)}


if __name__ == "__main__":
    mcp.run()
