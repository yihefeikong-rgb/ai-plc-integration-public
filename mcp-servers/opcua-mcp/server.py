"""
OPC UA MCP Server — 西门子 PLC 读写（阶段1：读 + 阶段2：写）
使用 FastMCP + asyncua
"""

from fastmcp import FastMCP
from asyncua import Client, ua
from config.settings import settings
from safety.validator import validator as safety_validator
from mcp_common.audit import audit

mcp = FastMCP("opcua-plc")
_client: Client | None = None


async def get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(url=settings.opcua_endpoint)
        if settings.opcua_username:
            _client.set_user(settings.opcua_username)
            _client.set_password(settings.opcua_password)
        await _client.connect()
    return _client


# ===== 阶段1：读取 =====

@mcp.tool()
async def read_tag(tag_name: str) -> dict:
    """读取单个 PLC 标签"""
    try:
        client = await get_client()
        node = client.get_node(tag_name)
        value = await node.read_value()
        audit.log("read", tag_name, str(value), success=True)
        return {"tag": tag_name, "value": value, "status": "ok"}
    except Exception as e:
        audit.log("read", tag_name, success=False, detail=str(e))
        return {"tag": tag_name, "error": str(e), "status": "error"}


@mcp.tool()
async def read_tags(tag_names: list[str]) -> list[dict]:
    """批量读取多个标签"""
    return [await read_tag(name) for name in tag_names]


@mcp.tool()
async def list_tags(root: str = "0:Objects") -> list[dict]:
    """浏览 OPC UA 地址空间"""
    try:
        client = await get_client()
        node = client.get_node(root)
        children = []
        for child in await node.get_children():
            name = (await child.read_browse_name()).Name
            try:
                val = await child.read_value()
            except Exception:
                val = "N/A"
            children.append({"name": name, "node_id": str(child), "value": str(val)})
        return children
    except Exception as e:
        return [{"error": str(e)}]


# ===== 阶段2：写入（带安全校验）=====

@mcp.tool()
async def write_tag(tag_name: str, value, operator: str = "ai-agent") -> dict:
    """写入标签（通过安全校验）"""
    try:
        client = await get_client()
        node = client.get_node(tag_name)
        current = await node.read_value()
    except Exception:
        current = None

    result = safety_validator.validate(tag_name, value, current)
    if not result.allowed:
        audit.log("write_blocked", tag_name, str(value), operator=operator,
                  success=False, detail=result.reason)
        return {"tag": tag_name, "status": "blocked", "reason": result.reason}

    try:
        variant = ua.DataValue(ua.Variant(value, await node.read_data_type_as_variant_type()))
        await node.write_value(variant)
        audit.log("write", tag_name, str(value), operator=operator, success=True)
        return {"tag": tag_name, "value": value, "status": "ok",
                "needs_confirmation": result.needs_confirmation}
    except Exception as e:
        audit.log("write", tag_name, str(value), operator=operator,
                  success=False, detail=str(e))
        safety_validator.record_error()
        return {"tag": tag_name, "status": "error", "error": str(e)}


if __name__ == "__main__":
    mcp.run()
