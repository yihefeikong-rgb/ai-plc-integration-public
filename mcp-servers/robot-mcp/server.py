"""
Robot MCP Server — 工业机器人控制（阶段4）

通过 OPC UA 连接 PLCSIM / S7-1500，控制 Factory I/O 中的 3D 机器人场景。
当前支持 Factory I/O「Pick & Place (Basic)」场景的二轴气动机械手。

架构:
  Claude/AI → robot-mcp (FastMCP) → OPC UA → PLCSIM Advanced → Factory I/O 机器人场景

I/O 映射 (Pick & Place Basic):
  %I0.0  ← Item at entry    (传感器: 入口有料)
  %I0.1  ← Item at exit     (传感器: 出口有料)
  %I0.2  ← Moving X         (传感器: X轴极限)
  %I0.3  ← Moving Z         (传感器: Z轴极限)
  %I0.4  ← Item detected    (传感器: 抓取检测)
  %I0.5  ← Start             (按钮)
  %I0.6  ← Reset             (按钮)
  %I0.7  ← Stop              (按钮)
  %I0.8  ← Emergency stop    (急停)
  %I0.9  ← Auto / Manual     (模式选择)

  %Q0.0  → Entry conveyor    (执行器: 入口传送带)
  %Q0.1  → Exit conveyor     (执行器: 出口传送带)
  %Q0.2  → Move X            (执行器: 机械臂X轴伸出/缩回)
  %Q0.3  → Move Z            (执行器: 机械臂Z轴下降/上升)
  %Q0.4  → Grab              (执行器: 夹爪抓紧/松开)
  %Q0.5  → Start light       (指示灯)
  %Q0.6  → Reset light       (指示灯)
  %Q0.7  → Stop light        (指示灯)

使用方式:
  1. 启动 PLCSIM Advanced V8.0，恢复实例 factoryio
  2. 打开 Factory I/O → 加载 Pick & Place (Basic) 场景
  3. F4 → 选 S7-PLCSIM 驱动 → 连接实例
  4. 启动 robot-mcp: python mcp-servers/robot-mcp/server.py
  5. AI 通过 MCP 工具控制机器人
"""

from __future__ import annotations
import asyncio
import sys
import json
from pathlib import Path
from fastmcp import FastMCP

# ── 通信后端: 优先 OPC UA, 回退 snap7 ──────────────────────────────
HAS_ASYNCUA = False
HAS_SNAP7 = False

try:
    from asyncua import Client as OPCClient
    HAS_ASYNCUA = True
except ImportError:
    OPCClient = None  # type: ignore

try:
    import snap7
    HAS_SNAP7 = True
except ImportError:
    pass

# ── 配置 ─────────────────────────────────────────────────────────────
PLC_IP = "192.168.0.1"
OPCUA_PORT = 4840
OPCUA_ENDPOINT = f"opc.tcp://{PLC_IP}:{OPCUA_PORT}"

# 从 config/settings 读取（如果项目已配置）
try:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from config.settings import settings
    OPCUA_ENDPOINT = settings.opcua_endpoint
    # 从 endpoint 提取 IP
    if "opc.tcp://" in OPCUA_ENDPOINT:
        PLC_IP = OPCUA_ENDPOINT.replace("opc.tcp://", "").split(":")[0]
except Exception:
    pass

# Pick & Place (Basic) 场景 I/O 映射
# 每种 I/O 支持两种寻址方式:
#  - node: OPC UA 节点路径（ns=4; s=...）
#  - byte/bit: S7 协议字节位寻址（byte, bit）
IO_MAP = {
    # Inputs (sensors)
    "sensor_entry":        {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.I0.0", "byte": 0, "bit": 0, "desc": "入口传感器"},
    "sensor_exit":         {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.I0.1", "byte": 0, "bit": 1, "desc": "出口传感器"},
    "sensor_moving_x":     {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.I0.2", "byte": 0, "bit": 2, "desc": "X轴移动中"},
    "sensor_moving_z":     {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.I0.3", "byte": 0, "bit": 3, "desc": "Z轴移动中"},
    "sensor_item_detected":{"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.I0.4", "byte": 0, "bit": 4, "desc": "抓取检测"},
    "sensor_start":        {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.I0.5", "byte": 0, "bit": 5, "desc": "启动按钮"},
    "sensor_reset":        {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.I0.6", "byte": 0, "bit": 6, "desc": "复位按钮"},
    "sensor_stop":         {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.I0.7", "byte": 0, "bit": 7, "desc": "停止按钮"},
    "sensor_estop":        {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.I0.8", "byte": 1, "bit": 0, "desc": "急停"},
    # Outputs (actuators)
    "conveyor_entry":      {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.Q0.0", "byte": 0, "bit": 0, "desc": "入口传送带"},
    "conveyor_exit":       {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.Q0.1", "byte": 0, "bit": 1, "desc": "出口传送带"},
    "arm_move_x":          {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.Q0.2", "byte": 0, "bit": 2, "desc": "机械臂X轴"},
    "arm_move_z":          {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.Q0.3", "byte": 0, "bit": 3, "desc": "机械臂Z轴"},
    "grab":                {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.Q0.4", "byte": 0, "bit": 4, "desc": "夹爪"},
    "start_light":         {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.Q0.5", "byte": 0, "bit": 5, "desc": "启动灯"},
    "reset_light":         {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.Q0.6", "byte": 0, "bit": 6, "desc": "复位灯"},
    "stop_light":          {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.Q0.7", "byte": 0, "bit": 7, "desc": "停止灯"},
}

# ── 后端类型 (自动选择) ──────────────────────────────────────────
# 'auto': 优先 OPC UA, 失败回退 snap7
# 'opcua': 强制 OPC UA
# 'snap7': 强制 snap7
BACKEND = "auto"

# ── FastMCP Server ──────────────────────────────────────────────────
mcp = FastMCP("robot-mcp")

# 后端连接
_opc_client: OPCClient | None = None
_snap_client: snap7.client.Client | None = None  # type: ignore
_backend_type: str | None = None  # 'opcua' 或 'snap7'


# ── 后端连接管理（OPC UA + snap7 双协议支持）────────────────────────

def get_backend_info() -> dict:
    """返回当前后端状态"""
    return {
        "backend": _backend_type or "not connected",
        "has_opcua": HAS_ASYNCUA,
        "has_snap7": HAS_SNAP7,
        "plc_ip": PLC_IP,
        "opcua_endpoint": OPCUA_ENDPOINT,
    }


async def _connect_opcua() -> bool:
    """连接 OPC UA 后端"""
    global _opc_client, _backend_type
    if not HAS_ASYNCUA:
        return False
    try:
        _opc_client = OPCClient(url=OPCUA_ENDPOINT)
        await _opc_client.connect()
        _backend_type = "opcua"
        return True
    except Exception:
        _opc_client = None
        return False


def _connect_snap7() -> bool:
    """连接 snap7 后端"""
    global _snap_client, _backend_type
    if not HAS_SNAP7:
        return False
    try:
        _snap_client = snap7.client.Client()
        _snap_client.connect(PLC_IP, 0, 1)
        if _snap_client.get_connected():
            _backend_type = "snap7"
            return True
    except Exception:
        pass
    _snap_client = None
    return False


async def ensure_connected() -> bool:
    """确保至少有一种后端连接可用"""
    global _backend_type, _opc_client, _snap_client

    if BACKEND == "opcua":
        if _opc_client is not None:
            return True
        return await _connect_opcua()

    if BACKEND == "snap7":
        if _snap_client is not None:
            return True
        return _connect_snap7()

    # auto: OPC UA 优先，回退 snap7
    if _opc_client is not None:
        return True
    if await _connect_opcua():
        return True
    if _snap_client is not None:
        return True
    return _connect_snap7()


async def get_client():
    """保持向后兼容的 get_client（实际调用 ensure_connected）"""
    if not await ensure_connected():
        raise RuntimeError(
            f"无法连接到 PLC {PLC_IP}。请检查:\n"
            f"  1. PLCSIM Advanced 是否运行\n"
            f"  2. 实例 factoryio 是否 Start\n"
            f"  3. OPC UA (端口 {OPCUA_PORT}) 或 S7 (端口 102) 是否可达\n"
            f"  4. 防火墙是否阻止"
        )


async def read_io(name: str) -> bool | None:
    """读取单个 I/O 点的值（支持 OPC UA + snap7）"""
    if name not in IO_MAP:
        return None
    info = IO_MAP[name]
    try:
        if not await ensure_connected():
            return None

        if _backend_type == "opcua" and _opc_client:
            node = _opc_client.get_node(info["node"])
            val = await node.read_value()
            return bool(val)

        elif _backend_type == "snap7" and _snap_client:
            area = 0x81 if name.startswith("sensor_") else 0x82
            data = _snap_client.read_area(area, 0, info["byte"], 1)
            return bool(data[0] & (1 << info["bit"]))

        return None
    except Exception:
        return None


async def write_io(name: str, value: bool) -> dict:
    """写入单个 I/O 点（支持 OPC UA + snap7）"""
    if name not in IO_MAP:
        return {"status": "error", "error": f"未知 I/O: {name}"}
    info = IO_MAP[name]
    try:
        if not await ensure_connected():
            return {"status": "error", "error": "未连接到 PLC"}

        if _backend_type == "opcua" and _opc_client:
            node = _opc_client.get_node(info["node"])
            from asyncua import ua
            await node.write_value(ua.DataValue(ua.Variant(value, ua.VariantType.Boolean)))
            return {"status": "ok", "io": name, "value": value, "backend": "opcua"}

        elif _backend_type == "snap7" and _snap_client:
            data = bytearray(_snap_client.read_area(0x82, 0, info["byte"], 1))
            if value:
                data[0] |= (1 << info["bit"])
            else:
                data[0] &= ~(1 << info["bit"])
            _snap_client.write_area(0x82, 0, info["byte"], bytes(data))
            return {"status": "ok", "io": name, "value": value, "backend": "snap7"}

        return {"status": "error", "error": f"无可用后端"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def read_all_inputs() -> dict:
    """批量读取所有输入传感器"""
    inputs = {}
    # snap7 优化：一次读 2 字节
    if _backend_type == "snap7" and _snap_client:
        try:
            data = _snap_client.read_area(0x81, 0, 0, 2)
            for name, info in IO_MAP.items():
                if name.startswith("sensor_"):
                    inputs[name] = bool(data[info["byte"]] & (1 << info["bit"]))
            return inputs
        except Exception:
            pass
    # 逐个读取（OPC UA 或兜底）
    for name in IO_MAP:
        if name.startswith("sensor_"):
            inputs[name] = await read_io(name)
    return inputs


async def wait_for(io_name: str, target: bool, timeout: float = 5.0, interval: float = 0.1) -> bool:
    """等待 I/O 点变为目标值，超时返回 False"""
    try:
        for _ in range(int(timeout / interval)):
            val = await read_io(io_name)
            if val == target:
                return True
            await asyncio.sleep(interval)
    except Exception:
        pass
    return False


async def ensure_disconnected():
    """确保所有输出复位（安全关停）"""
    for name in ["conveyor_entry", "conveyor_exit", "arm_move_x", "arm_move_z", "grab"]:
        try:
            await write_io(name, False)
        except Exception:
            pass


# ═════════════════════════════════════════════════════════════════════
# MCP 工具
# ═════════════════════════════════════════════════════════════════════


@mcp.tool()
async def get_status() -> dict:
    """获取机器人当前状态：传感器值、急停、连接状态"""
    try:
        await ensure_connected()
        conn = f"connected ({_backend_type})"
    except Exception as e:
        conn = f"error: {e}"

    sensors = await read_all_inputs()
    position = "unknown"
    if sensors.get("sensor_moving_x") is True:
        position = "extended"
    elif sensors.get("sensor_moving_x") is False:
        position = "retracted"

    return {
        "connection": conn,
        "backend": _backend_type or "none",
        "plc_ip": PLC_IP,
        "scene": "Pick & Place (Basic)",
        "sensors": sensors,
        "estimated_position": position,
        "emergency_stop": sensors.get("sensor_estop"),
    }


@mcp.tool()
async def go_home() -> dict:
    """将机器人恢复到安全起始位置：X收回、Z升起、夹爪松开、传送带停止"""
    try:
        # 1. 松开夹爪
        await write_io("grab", False)
        await asyncio.sleep(0.3)

        # 2. Z轴升起（假设上升是 False）
        await write_io("arm_move_z", False)
        await asyncio.sleep(0.5)

        # 3. X轴收回（假设收回是 False）
        await write_io("arm_move_x", False)
        await asyncio.sleep(0.5)

        # 4. 停止所有传送带
        await write_io("conveyor_entry", False)
        await write_io("conveyor_exit", False)

        return {"status": "ok", "position": "home", "message": "机器人已回到起始位置"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
async def pick_item() -> dict:
    """
    从入口传送带拾取物品。
    流程: 等待物料到位 → X伸出 → Z下降 → 夹爪闭合 → Z上升 → X收回
    """
    try:
        # 检查急停
        estop = await read_io("sensor_estop")
        if estop:
            return {"status": "error", "error": "急停已触发，无法执行"}

        # 检查是否有物料已到位
        has_item = await read_io("sensor_entry")
        if not has_item:
            # 尝试运行入口传送带送料
            await write_io("conveyor_entry", True)
            arrived = await wait_for("sensor_entry", True, timeout=3.0)
            if not arrived:
                await write_io("conveyor_entry", False)
                return {"status": "error", "error": "入口无物料，等待超时。请确保场景已启动且入口有料"}

        # 停传送带
        await write_io("conveyor_entry", False)
        await asyncio.sleep(0.2)

        # 1. X轴伸出
        await write_io("arm_move_x", True)
        x_ok = await wait_for("sensor_moving_x", True, timeout=3.0)
        if not x_ok:
            await go_home()
            return {"status": "error", "error": "X轴伸出超时，已回位"}
        await asyncio.sleep(0.3)

        # 2. Z轴下降
        await write_io("arm_move_z", True)
        z_ok = await wait_for("sensor_moving_z", True, timeout=3.0)
        if not z_ok:
            await go_home()
            return {"status": "error", "error": "Z轴下降超时，已回位"}
        await asyncio.sleep(0.3)

        # 3. 夹爪闭合
        await write_io("grab", True)
        await asyncio.sleep(0.5)

        # 确认抓到
        detected = await read_io("sensor_item_detected")
        if not detected:
            await write_io("grab", False)
            await go_home()
            return {"status": "error", "error": "抓取失败（未检测到物料），已复位"}

        # 4. Z轴上升
        await write_io("arm_move_z", False)
        await wait_for("sensor_moving_z", False, timeout=3.0)
        await asyncio.sleep(0.3)

        # 5. X轴收回
        await write_io("arm_move_x", False)
        await wait_for("sensor_moving_x", False, timeout=3.0)
        await asyncio.sleep(0.3)

        return {"status": "ok", "action": "pick", "message": "物料已抓取，机械臂已收回"}
    except Exception as e:
        await go_home()
        return {"status": "error", "error": f"抓取异常: {e}，已复位"}


@mcp.tool()
async def place_item() -> dict:
    """
    将抓取的物料放置到出口传送带。
    流程: X伸出 → Z下降 → 夹爪松开 → Z上升 → X收回 → 启动出口传送带
    """
    try:
        estop = await read_io("sensor_estop")
        if estop:
            return {"status": "error", "error": "急停已触发"}

        has_item = await read_io("sensor_item_detected")
        if not has_item:
            return {"status": "error", "error": "夹爪中无物料，请先执行 pick_item()"}

        # 1. X轴伸出（到出口位置）
        await write_io("arm_move_x", True)
        await wait_for("sensor_moving_x", True, timeout=3.0)
        await asyncio.sleep(0.3)

        # 2. Z轴下降
        await write_io("arm_move_z", True)
        await wait_for("sensor_moving_z", True, timeout=3.0)
        await asyncio.sleep(0.3)

        # 3. 夹爪松开
        await write_io("grab", False)
        await asyncio.sleep(0.5)

        # 4. Z轴上升
        await write_io("arm_move_z", False)
        await wait_for("sensor_moving_z", False, timeout=3.0)
        await asyncio.sleep(0.3)

        # 5. X轴收回
        await write_io("arm_move_x", False)
        await wait_for("sensor_moving_x", False, timeout=3.0)
        await asyncio.sleep(0.3)

        # 6. 启动出口传送带运走物品
        await write_io("conveyor_exit", True)
        await asyncio.sleep(2.0)
        await write_io("conveyor_exit", False)

        return {"status": "ok", "action": "place", "message": "物料已放置到出口，已运走"}
    except Exception as e:
        await go_home()
        return {"status": "error", "error": f"放置异常: {e}，已复位"}


@mcp.tool()
async def move_arm_to(position: str) -> dict:
    """
    将机械臂移动到指定位置。

    参数:
      position: 目标位置
        - "home"    → X收回, Z升起, 夹爪松开（默认安全位）
        - "pick"    → X伸出, Z下降, 夹爪张开（拾取准备位）
        - "extend"  → 仅X伸出（到出口位置）
        - "retract" → 仅X收回（回入口位置）
        - "lower"   → 仅Z下降
        - "raise"   → 仅Z上升
    """
    valid = ["home", "pick", "extend", "retract", "lower", "raise"]
    if position not in valid:
        return {"status": "error", "error": f"无效位置: {position}。可选: {', '.join(valid)}"}

    try:
        if position == "home":
            await write_io("grab", False)
            await asyncio.sleep(0.2)
            await write_io("arm_move_z", False)
            await asyncio.sleep(0.3)
            await write_io("arm_move_x", False)
            await asyncio.sleep(0.3)

        elif position == "pick":
            await write_io("arm_move_x", True)
            await wait_for("sensor_moving_x", True, timeout=3.0)
            await asyncio.sleep(0.2)
            await write_io("arm_move_z", True)
            await wait_for("sensor_moving_z", True, timeout=3.0)
            await asyncio.sleep(0.2)
            await write_io("grab", False)

        elif position == "extend":
            await write_io("arm_move_x", True)
            await wait_for("sensor_moving_x", True, timeout=3.0)

        elif position == "retract":
            await write_io("arm_move_x", False)
            await wait_for("sensor_moving_x", False, timeout=3.0)

        elif position == "lower":
            await write_io("arm_move_z", True)
            await wait_for("sensor_moving_z", True, timeout=3.0)

        elif position == "raise":
            await write_io("arm_move_z", False)
            await wait_for("sensor_moving_z", False, timeout=3.0)

        return {"status": "ok", "action": "move_to", "position": position,
                "message": f"机械臂已移动到 {position}"}
    except Exception as e:
        await go_home()
        return {"status": "error", "error": f"移动异常: {e}，已复位"}


@mcp.tool()
async def run_pick_cycle(count: int = 1) -> dict:
    """
    执行完整的 pick-and-place 循环（自动重复）。

    参数:
      count: 循环次数（1-10，默认1次）
    """
    count = max(1, min(count, 10))
    results = []
    try:
        for i in range(count):
            pick_result = await pick_item()
            results.append({"cycle": i + 1, "step": "pick", "result": pick_result})
            if pick_result.get("status") != "ok":
                break
            place_result = await place_item()
            results.append({"cycle": i + 1, "step": "place", "result": place_result})
            if place_result.get("status") != "ok":
                break

        return {"status": "ok", "cycles_completed": len([r for r in results if r["result"].get("status") == "ok"]),
                "total_requested": count, "details": results}
    except Exception as e:
        await go_home()
        return {"status": "error", "error": f"循环异常: {e}", "partial_results": results}


@mcp.tool()
async def control_conveyor(direction: str = "stop") -> dict:
    """
    控制传送带。

    参数:
      direction: "entry" → 入口传送带启动
                 "exit"  → 出口传送带启动
                 "stop"  → 全部停止
    """
    try:
        if direction == "entry":
            await write_io("conveyor_entry", True)
            await write_io("conveyor_exit", False)
        elif direction == "exit":
            await write_io("conveyor_entry", False)
            await write_io("conveyor_exit", True)
        else:
            await write_io("conveyor_entry", False)
            await write_io("conveyor_exit", False)
        return {"status": "ok", "direction": direction}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ═════════════════════════════════════════════════════════════════════
# CLI 入口
# ═════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Robot MCP Server — 工业机器人控制")
    parser.add_argument("--endpoint", default=None,
                        help=f"OPC UA 端点 (默认: {OPCUA_ENDPOINT})")
    parser.add_argument("--ip", default=PLC_IP,
                        help=f"PLC IP 地址 (默认: {PLC_IP})")
    parser.add_argument("--backend", default="auto",
                        choices=["auto", "opcua", "snap7"],
                        help="通信后端 (默认: auto, 自动选择)")
    parser.add_argument("--scene", default="Pick & Place (Basic)",
                        choices=["Pick & Place (Basic)", "Palletizer"],
                        help="Factory I/O 场景 (默认: Pick & Place (Basic))")
    args = parser.parse_args()

    if args.endpoint:
        OPCUA_ENDPOINT = args.endpoint
        if "opc.tcp://" in OPCUA_ENDPOINT:
            PLC_IP = OPCUA_ENDPOINT.replace("opc.tcp://", "").split(":")[0]
            if ":" in OPCUA_ENDPOINT.split(":")[-1]:
                OPCUA_PORT = int(OPCUA_ENDPOINT.split(":")[-1])
            else:
                OPCUA_PORT = 4840
    if args.ip:
        PLC_IP = args.ip
        OPCUA_ENDPOINT = f"opc.tcp://{PLC_IP}:4840"
    BACKEND = args.backend

    print(f"  Robot MCP Server starting...")
    print(f"  场景: {args.scene}")
    print(f"  PLC IP: {PLC_IP}")
    print(f"  后端: {BACKEND} (OPC UA={HAS_ASYNCUA}, snap7={HAS_SNAP7})")
    print(f"  机器人指令: get_status, go_home, pick_item, place_item, move_arm_to, control_conveyor, run_pick_cycle")
    mcp.run()
