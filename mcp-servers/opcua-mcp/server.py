#!/usr/bin/env python3
"""
OPC UA MCP Server — AI 通过 OPC UA 协议读写 PLC 变量

架构:
  AI(Claude) ←→ stdio MCP ←→ 本服务器 ←→ asyncua ←→ PLC (S7-1200/1500)

安全原则:
  - 所有写入操作必须先检查互锁条件
  - 连续 3 次异常值自动熔断
  - 所有操作记录审计日志

用法:
  python server.py              # stdio 模式（给 Claude Code 用）
  python server.py --test       # 测试连接
"""
import sys
from typing import Optional
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("❌ 请安装 mcp: pip install mcp", file=sys.stderr)
    sys.exit(1)

try:
    from asyncua import Client, ua
    ASYNCUA_AVAILABLE = True
except ImportError:
    ASYNCUA_AVAILABLE = False

# 导入本地安全模块
sys.path.insert(0, str(Path(__file__).parent))
import safety

# ── 全局状态 ──
mcp = FastMCP("opcua_plc")
_client: Optional[object] = None
_endpoint: str = ""


# ═══════════════════════════════════════
#  连接管理
# ═══════════════════════════════════════

@mcp.tool(
    name="opcua_connect",
    annotations={"destructiveHint": False},
)
async def connect(endpoint: str = "opc.tcp://192.168.0.1:4840") -> str:
    """连接到 OPC UA 服务器（西门子 PLC 默认端口 4840）

    Args:
        endpoint: OPC UA 端点地址
    """
    global _client, _endpoint

    if not ASYNCUA_AVAILABLE:
        return "❌ asyncua 未安装。请运行: pip install asyncua"

    if _client is not None:
        return f"⚠ 已连接到 {_endpoint}，请先断开"

    try:
        client = Client(url=endpoint)
        await client.connect()
        _client = client
        _endpoint = endpoint
        return f"✅ 已连接到 {endpoint}"
    except Exception as e:
        return f"❌ 连接失败: {e}"


@mcp.tool(
    name="opcua_disconnect",
    annotations={"destructiveHint": False},
)
async def disconnect() -> str:
    """断开 OPC UA 连接"""
    global _client, _endpoint

    if _client is None:
        return "⚠ 未连接"

    try:
        await _client.disconnect()
    except Exception:
        pass
    _client = None
    old = _endpoint
    _endpoint = ""
    return f"✅ 已断开 {old}"


@mcp.tool(
    name="opcua_get_status",
    annotations={"readOnlyHint": True},
)
async def get_status() -> str:
    """获取 OPC UA 连接状态和安全信息"""
    fuse = safety.get_fuse_status()
    status_lines = [
        f"asyncua: {'可用' if ASYNCUA_AVAILABLE else '未安装'}",
        f"连接: {'已连接 → ' + _endpoint if _client else '未连接'}",
        f"熔断器: {'🔴 已触发 — ' + fuse['trip_reason'] if fuse['tripped'] else '🟢 正常'}",
        f"连续错误: {fuse['consecutive_errors']}/{fuse['max_errors']}",
    ]
    return "\n".join(status_lines)


# ═══════════════════════════════════════
#  读取工具
# ═══════════════════════════════════════

@mcp.tool(
    name="opcua_read",
    annotations={"readOnlyHint": True},
)
async def read_node(node_id: str) -> str:
    """读取 OPC UA 节点的当前值

    Args:
        node_id: 节点标识符，如 "ns=3;s=DB1.MotorSpeed" 或 "ns=3;i=100"
    """
    if _client is None:
        return "❌ 未连接，请先调用 opcua_connect"

    try:
        node = _client.get_node(node_id)
        value = await node.read_value()
        dtype = await node.read_data_type_as_variant_type()
        return f"节点: {node_id}\n值: {value}\n类型: {dtype.name}"
    except Exception as e:
        return f"❌ 读取失败 [{node_id}]: {e}"


@mcp.tool(
    name="opcua_browse",
    annotations={"readOnlyHint": True},
)
async def browse(node_id: str = "ns=0;i=85", depth: int = 2) -> str:
    """浏览 OPC UA 节点树结构

    Args:
        node_id: 起始节点（默认 Objects 文件夹 ns=0;i=85）
        depth: 浏览深度（默认 2 层）
    """
    if _client is None:
        return "❌ 未连接，请先调用 opcua_connect"

    try:
        node = _client.get_node(node_id)
        lines = []
        await _browse_recursive(node, lines, depth, 0)
        return "\n".join(lines) if lines else "（空节点）"
    except Exception as e:
        return f"❌ 浏览失败: {e}"


async def _browse_recursive(node, lines: list, max_depth: int, current_depth: int):
    """递归浏览节点树"""
    if current_depth >= max_depth:
        return
    try:
        children = await node.get_children()
        for child in children[:50]:  # 限制每层最多50个
            name = (await child.read_browse_name()).Name
            indent = "  " * current_depth
            lines.append(f"{indent}├─ {name} [{child}]")
            await _browse_recursive(child, lines, max_depth, current_depth + 1)
    except Exception:
        pass


# ═══════════════════════════════════════
#  写入工具（带安全互锁）
# ═══════════════════════════════════════

@mcp.tool(
    name="opcua_write",
    annotations={"destructiveHint": True},
)
async def write_node(
    node_id: str,
    value: str,
    data_type: str = "auto",
) -> str:
    """写入 OPC UA 节点值（自动检查安全互锁）

    Args:
        node_id: 节点标识符
        value: 要写入的值（字符串形式）
        data_type: 数据类型 (auto/bool/int/float/string)

    安全机制:
        - 写入前自动检查互锁条件（急停、安全位）
        - 数值范围检查
        - 连续异常自动熔断
    """
    if _client is None:
        return "❌ 未连接，请先调用 opcua_connect"

    # 1. 互锁检查
    interlock_ok, interlock_reason = await safety.check_interlock(_client)
    if not interlock_ok:
        safety.record_write(node_id, value, False, interlock_reason)
        return f"🚫 写入被拒绝: {interlock_reason}"

    # 2. 范围检查
    range_ok, range_reason = safety.check_value_range(node_id, value)
    if not range_ok:
        safety.record_write(node_id, value, False, range_reason)
        return f"🚫 值超出范围: {range_reason}"

    # 3. 类型转换
    converted = _convert_value(value, data_type)

    # 4. 执行写入
    try:
        node = _client.get_node(node_id)
        if data_type == "auto":
            vtype = await node.read_data_type_as_variant_type()
            dv = ua.DataValue(ua.Variant(converted, vtype))
        else:
            dv = ua.DataValue(ua.Variant(converted))
        await node.write_value(dv)

        # 5. 读回验证
        readback = await node.read_value()
        safety.record_write(node_id, value, True)
        return f"✅ 已写入 {node_id} = {readback}"
    except Exception as e:
        safety.record_write(node_id, value, False, str(e))
        return f"❌ 写入失败: {e}"


@mcp.tool(
    name="opcua_reset_fuse",
    annotations={"destructiveHint": True},
)
async def reset_fuse() -> str:
    """重置安全熔断器（连续写入失败后自动触发熔断，需人工重置）"""
    result = safety.reset_fuse()
    return result


# ═══════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════

def _convert_value(value_str: str, data_type: str):
    """将字符串值转换为目标类型"""
    if data_type == "bool":
        return value_str.lower() in ("true", "1", "yes", "on")
    elif data_type == "int":
        return int(value_str)
    elif data_type == "float":
        return float(value_str)
    elif data_type == "string":
        return value_str
    else:  # auto — 尝试自动推断
        if value_str.lower() in ("true", "false"):
            return value_str.lower() == "true"
        try:
            return int(value_str)
        except ValueError:
            pass
        try:
            return float(value_str)
        except ValueError:
            pass
        return value_str


# ═══════════════════════════════════════
#  入口
# ═══════════════════════════════════════

if __name__ == "__main__":
    if "--test" in sys.argv:
        print("OPC UA MCP Server — 测试模式")
        print(f"asyncua: {'可用' if ASYNCUA_AVAILABLE else '未安装 (pip install asyncua)'}")
        print(f"安全模块: 已加载")
        print(f"熔断器: {safety.get_fuse_status()}")
    else:
        mcp.run(transport="stdio")
