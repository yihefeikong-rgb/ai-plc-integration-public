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
  %I0.8  ← Emergency-stop safety chain (TRUE=healthy, FALSE=active/fault)
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
import logging
import os
import sys
import json
import argparse
from pathlib import Path
from typing import Any
from fastmcp import FastMCP

logger = logging.getLogger("robot-mcp")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_common.control_target import (
    TargetConfigurationError,
    approved_opcua_endpoint,
    get_control_target,
    require_control_ip,
    require_opcua_endpoint,
)
from mcp_common.audit import AuditLogger, authenticated_actor
from safety.confirmation import ConfirmationError, ConfirmationService

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
PLC_IP = get_control_target().plc_ip
OPCUA_PORT = 4840
OPCUA_ENDPOINT = approved_opcua_endpoint()

# 急停重确认闩锁的持久化文件。设置 ROBOT_ESTOP_LATCH_FILE 后，闩锁跨进程
# 重启保持：服务重启不会静默清除"急停恢复必须重新确认"要求。未设置时仅
# 存进程内存（兼容原有行为）。模拟/离线测试不设置该变量，避免污染测试环境。
_ESTOP_LATCH_FILE = (
    Path(os.environ["ROBOT_ESTOP_LATCH_FILE"]) if os.environ.get("ROBOT_ESTOP_LATCH_FILE") else None
)

# Pick & Place (Basic) 场景 I/O 映射
# 每种 I/O 支持两种寻址方式:
#  - node: OPC UA 节点路径（ns=4; s=...），必须与本模块部署的 pnp_tags.json
#          标签名一致（下划线命名：I0_0 / I0_8 / Q0_0，而非 I0.0 / I0.8 / Q0.0）。
#          点号命名无法解析为 PLCSIM Advanced 的 PLC 标签节点，会导致 OPC UA
#          后端所有读返回 None、急停被误判为未知并 fail-closed 拒绝动作。
#  - byte/bit: S7 协议字节位寻址（byte, bit）
IO_MAP = {
    # Inputs (sensors)
    "sensor_entry":        {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.I0_0", "byte": 0, "bit": 0, "desc": "入口传感器"},
    "sensor_exit":         {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.I0_1", "byte": 0, "bit": 1, "desc": "出口传感器"},
    "sensor_moving_x":     {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.I0_2", "byte": 0, "bit": 2, "desc": "X轴移动中"},
    "sensor_moving_z":     {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.I0_3", "byte": 0, "bit": 3, "desc": "Z轴移动中"},
    "sensor_item_detected":{"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.I0_4", "byte": 0, "bit": 4, "desc": "抓取检测"},
    "sensor_start":        {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.I0_5", "byte": 0, "bit": 5, "desc": "启动按钮"},
    "sensor_reset":        {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.I0_6", "byte": 0, "bit": 6, "desc": "复位按钮"},
    "sensor_stop":         {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.I0_7", "byte": 0, "bit": 7, "desc": "停止按钮"},
    "sensor_estop":        {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.I0_8", "byte": 1, "bit": 0, "desc": "急停安全回路（TRUE=健康）"},
    # Outputs (actuators)
    "conveyor_entry":      {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.Q0_0", "byte": 0, "bit": 0, "desc": "入口传送带"},
    "conveyor_exit":       {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.Q0_1", "byte": 0, "bit": 1, "desc": "出口传送带"},
    "arm_move_x":          {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.Q0_2", "byte": 0, "bit": 2, "desc": "机械臂X轴"},
    "arm_move_z":          {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.Q0_3", "byte": 0, "bit": 3, "desc": "机械臂Z轴"},
    "grab":                {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.Q0_4", "byte": 0, "bit": 4, "desc": "夹爪"},
    "start_light":         {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.Q0_5", "byte": 0, "bit": 5, "desc": "启动灯"},
    "reset_light":         {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.Q0_6", "byte": 0, "bit": 6, "desc": "复位灯"},
    "stop_light":          {"node": "ns=4;s=|var|PLC.PROGRAM.PLC_PROGRAM.Q0_7", "byte": 0, "bit": 7, "desc": "停止灯"},
}


class RobotBackend:
    """机器人 PLC 后端连接管理器（OPC UA + snap7 + simulated 三模式）"""

    def __init__(self):
        self._opc_client: Any = None
        self._snap_client: Any = None
        self._backend_type: str | None = None
        # 模拟状态存储（simulated 后端模式）
        self._sim_state: dict[str, Any] = {
            "sensor_estop": True,
            "sensor_entry": False,
            "sensor_exit": False,
            "sensor_moving_x": False,
            "sensor_moving_z": False,
            "sensor_item_detected": False,
            "sensor_start": False,
            "sensor_reset": False,
            "sensor_stop": False,
            "conveyor_entry": False,
            "conveyor_exit": False,
            "arm_move_x": False,
            "arm_move_z": False,
            "grab": False,
            "start_light": False,
            "reset_light": False,
            "stop_light": False,
        }
        self._estop_reset_required = False
        self._latch_loaded = False

    @property
    def backend_type(self) -> str | None:
        return self._backend_type

    async def connect_opcua(self) -> bool:
        if not HAS_ASYNCUA:
            return False
        try:
            self._opc_client = OPCClient(url=OPCUA_ENDPOINT)
            await self._opc_client.connect()
            self._backend_type = "opcua"
            return True
        except Exception as exc:
            logger.error("OPC UA 连接失败（%s）: %s", OPCUA_ENDPOINT, exc)
            try:
                if self._opc_client is not None:
                    await self._opc_client.disconnect()
            except Exception:
                pass
            self._opc_client = None
            return False

    def connect_snap7(self) -> bool:
        if not HAS_SNAP7:
            return False
        try:
            self._snap_client = snap7.client.Client()
            self._snap_client.connect(PLC_IP, 0, 1)
            if self._snap_client.get_connected():
                self._backend_type = "snap7"
                return True
        except Exception as exc:
            logger.error("snap7 连接失败（%s）: %s", PLC_IP, exc)
        self._snap_client = None
        return False

    async def connect_simulated(self) -> bool:
        """模拟连接 — 直接标记为已连接，无需硬件"""
        self._backend_type = "simulated"
        return True

    def _update_sim_dependencies(self, name: str, value: bool) -> None:
        """模拟联动逻辑 — 写入执行器时自动更新关联传感器"""
        if name == "grab" and value:
            # 夹爪闭合时，模拟检测到物料（前提是有物料在附近）
            self._sim_state["sensor_item_detected"] = True
        elif name == "grab" and not value:
            self._sim_state["sensor_item_detected"] = False
        elif name == "arm_move_x" and value:
            self._sim_state["sensor_moving_x"] = True
        elif name == "arm_move_x" and not value:
            self._sim_state["sensor_moving_x"] = False
        elif name == "arm_move_z" and value:
            self._sim_state["sensor_moving_z"] = True
        elif name == "arm_move_z" and not value:
            self._sim_state["sensor_moving_z"] = False

    async def ensure_connected(self) -> bool:
        if BACKEND == "simulated":
            if self._backend_type == "simulated":
                return True
            return await self.connect_simulated()
        if BACKEND == "opcua":
            if self._opc_client is not None:
                return True
            return await self.connect_opcua()
        if BACKEND == "snap7":
            if self._snap_client is not None:
                return True
            # snap7 connect 是同步阻塞调用，放到线程池执行，避免卡死事件循环
            return await asyncio.to_thread(self.connect_snap7)
        # auto
        if self._opc_client is not None:
            return True
        if await self.connect_opcua():
            return True
        if self._snap_client is not None:
            return True
        return await asyncio.to_thread(self.connect_snap7)

    async def get_client(self):
        if not await self.ensure_connected():
            raise RuntimeError(
                f"无法连接到 PLC {PLC_IP}。请检查:\n"
                f"  1. PLCSIM Advanced 是否运行\n"
                f"  2. 实例 factoryio 是否 Start\n"
                f"  3. OPC UA (端口 {OPCUA_PORT}) 或 S7 (端口 102) 是否可达\n"
                f"  4. 防火墙是否阻止"
            )

    async def _drop_opcua(self) -> None:
        """丢弃失效的 OPC UA 客户端，使下一次 ensure_connected 重连或回退 snap7。"""
        client, self._opc_client = self._opc_client, None
        self._backend_type = None
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass

    def _load_estop_latch(self) -> bool:
        """从持久化文件加载急停重确认闩锁（fail-closed：读取失败视为急停激活）。"""
        if not _ESTOP_LATCH_FILE:
            return False
        try:
            if _ESTOP_LATCH_FILE.exists():
                data = json.loads(_ESTOP_LATCH_FILE.read_text(encoding="utf-8"))
                return bool(data.get("estop_reset_required", False))
        except Exception as exc:
            # fail-closed：无法确认闩锁状态时按急停激活处理，绝不静默放行
            logger.error("急停闩锁读取失败，按急停激活处理: %s", exc)
            return True
        return False

    def _save_estop_latch(self) -> None:
        """持久化急停重确认闩锁；模拟模式不落盘（避免污染离线测试）。"""
        if not _ESTOP_LATCH_FILE:
            return
        if self._backend_type == "simulated":
            return
        try:
            _ESTOP_LATCH_FILE.parent.mkdir(parents=True, exist_ok=True)
            _ESTOP_LATCH_FILE.write_text(
                json.dumps({"estop_reset_required": bool(self._estop_reset_required)}),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("急停闩锁持久化失败: %s", exc)

    async def read_io(self, name: str) -> bool | None:
        if name not in IO_MAP:
            return None
        info = IO_MAP[name]
        try:
            if not await self.ensure_connected():
                return None
            if self._backend_type == "simulated":
                return bool(self._sim_state.get(name, False))
            elif self._backend_type == "opcua" and self._opc_client:
                try:
                    node = self._opc_client.get_node(info["node"])
                    val = await node.read_value()
                    return bool(val)
                except Exception:
                    # OPC UA 读失败：丢弃失效客户端，下次调用自动重连/回退 snap7
                    await self._drop_opcua()
                    return None
            elif self._backend_type == "snap7" and self._snap_client:
                area = 0x81 if name.startswith("sensor_") else 0x82
                data = self._snap_client.read_area(area, 0, info["byte"], 1)
                return bool(data[0] & (1 << info["bit"]))
            return None
        except Exception as exc:
            logger.debug("读取 %s 失败: %s", name, exc)
            return None

    async def motion_permission_error(self) -> str | None:
        """返回动作使能前的安全阻断原因；安全停止命令不受此门禁影响。"""
        if self._backend_type != "simulated" and not self._latch_loaded:
            self._estop_reset_required = self._load_estop_latch()
            self._latch_loaded = True
        estop = await self.read_io("sensor_estop")
        if estop is not True:
            self._estop_reset_required = True
            self._save_estop_latch()
            return "急停安全回路未健康或状态未知，禁止使能输出"
        if self._estop_reset_required:
            return "急停恢复后必须重新确认，禁止使能输出"
        return None

    async def write_io(self, name: str, value: bool) -> dict:
        if name not in IO_MAP:
            return {"status": "error", "error": f"未知 I/O: {name}"}
        # 急停安全检查：TRUE 表示安全回路健康；FALSE、未知或通信失败均拒绝使能动作。
        if value and (name.startswith("conveyor_") or name.startswith("arm_") or name == "grab"):
            reason = await self.motion_permission_error()
            if reason:
                _audit("robot.write_io_blocked", io=name, value=bool(value), reason=reason)
                return {"status": "error", "error": reason}
        info = IO_MAP[name]
        try:
            if not await self.ensure_connected():
                return {"status": "error", "error": "未连接到 PLC"}
            if self._backend_type != "simulated":
                # 审计前置门（fail-closed）：真实执行器（opcua/snap7）写入前必须
                # 先成功写入 begin_control_operation 控制意图审计；审计链不可用时
                # 拒绝执行写入（对齐 opcua/modbus 兄弟服务器）。模拟后端为离线
                # 测试兼容路径，不设此门。
                gate_reason = _begin_write_audit(name, value)
                if gate_reason:
                    logger.error("写入 %s=%s 被审计前置门阻断", name, value)
                    return {"status": "error", "error": gate_reason}
            if self._backend_type == "simulated":
                # 模拟模式下急停闩锁置位后禁止直接把急停置健康，防止自愈绕过
                if name == "sensor_estop" and value and self._estop_reset_required:
                    _audit("robot.write_io_blocked", io=name, value=bool(value),
                           reason="模拟模式禁止直接解除急停")
                    return {"status": "error", "error": "急停恢复后必须重新确认，禁止直接置健康"}
                self._sim_state[name] = value
                self._update_sim_dependencies(name, value)
                result = {"status": "ok", "io": name, "value": value, "backend": "simulated"}
            elif self._backend_type == "opcua" and self._opc_client:
                try:
                    node = self._opc_client.get_node(info["node"])
                    from asyncua import ua
                    await node.write_value(ua.DataValue(ua.Variant(value, ua.VariantType.Boolean)))
                except Exception:
                    await self._drop_opcua()
                    _audit("robot.write_io", io=name, value=bool(value), result="error",
                           error="OPC UA 写入失败，连接已重置")
                    return {"status": "error", "error": "OPC UA 写入失败，连接已重置"}
                result = {"status": "ok", "io": name, "value": value, "backend": "opcua"}
            elif self._backend_type == "snap7" and self._snap_client:
                # 输出字节每次写前必须从 PLC 读回（读-改-写）：PLC 每周期驱动输出
                # （急停/未复位时强制清零 Q0.0-Q0.4，正常时驱动指示灯 Q0.5/Q0.7），
                # 复用陈旧缓存会把急停期间 PLC 已清零的执行器位重新置位。读回失败时
                # fail-closed 拒绝写入，不用猜测字节覆盖 PLC 输出。
                try:
                    data = bytearray(
                        self._snap_client.read_area(0x82, 0, info["byte"], 1)
                    )
                except Exception as exc:
                    logger.warning("snap7 读回输出字节失败: %s", exc)
                    _audit("robot.write_io", io=name, value=bool(value), result="error",
                           error="snap7 读回输出失败，写入已中止")
                    return {"status": "error", "error": "snap7 读回输出失败，写入已中止"}
                if value:
                    data[0] |= (1 << info["bit"])
                else:
                    data[0] &= ~(1 << info["bit"])
                self._snap_client.write_area(0x82, 0, info["byte"], bytes(data))
                result = {"status": "ok", "io": name, "value": value, "backend": "snap7"}
            else:
                return {"status": "error", "error": "无可用后端"}
            _audit("robot.write_io", io=name, value=bool(value),
                   backend=self._backend_type, result=result["status"])
            return result
        except Exception as exc:
            logger.error("写入 %s=%s 失败: %s", name, value, exc)
            return {"status": "error", "error": "写入失败，请检查连接"}

    async def confirm_estop_recovery(self) -> dict:
        """在人工确认急停已恢复后解除动作闭锁。

        真实后端（OPC UA/snap7）还要求 PLC 复位按钮（I0.6）已按下，作为
        人工现场确认的物理证据——急停恢复必须由人工执行，不允许 AI 自行确认。
        模拟后端没有物理证据：确认动作本身即视为人工恢复，并复位模拟急停输入；
        否则 write_io 的防自愈门禁（_estop_reset_required 置位后禁止直接写健康）
        与"确认前置要求急停已健康"互相排斥，急停后无法通过公开 API 恢复。
        """
        if self._backend_type != "simulated" and not self._latch_loaded:
            self._estop_reset_required = self._load_estop_latch()
            self._latch_loaded = True
        if self._backend_type == "simulated":
            # 模拟模式：人工确认即恢复，把模拟急停输入复位为健康
            self._sim_state["sensor_estop"] = True
        estop = await self.read_io("sensor_estop")
        if estop is not True:
            self._estop_reset_required = True
            self._save_estop_latch()
            return {"status": "error", "error": "急停安全回路未健康或状态未知，不能确认恢复"}
        if self._backend_type != "simulated":
            reset = await self.read_io("sensor_reset")
            if reset is not True:
                return {"status": "error", "error": "未检测到复位按钮（I0.6）信号，急停恢复必须由人工现场按复位确认"}
        self._estop_reset_required = False
        self._save_estop_latch()
        _audit("robot.estop_recovery", backend=self._backend_type, result="ok")
        return {"status": "ok", "message": "急停安全回路已确认恢复"}

    async def read_all_inputs(self) -> dict:
        inputs = {}
        if self._backend_type == "simulated":
            for name in IO_MAP:
                if name.startswith("sensor_"):
                    inputs[name] = bool(self._sim_state.get(name, False))
            return inputs
        if self._backend_type == "snap7" and self._snap_client:
            try:
                data = self._snap_client.read_area(0x81, 0, 0, 2)
                for name, info in IO_MAP.items():
                    if name.startswith("sensor_"):
                        inputs[name] = bool(data[info["byte"]] & (1 << info["bit"]))
                return inputs
            except Exception as exc:
                logger.warning("snap7 批量读取输入失败，降级逐点读取: %s", exc)
        if self._backend_type == "opcua" and self._opc_client:
            # OPC UA 一次 read_values 批量读取全部传感器节点，避免 N+1 次串行往返
            sensor_items = [(name, info) for name, info in IO_MAP.items() if name.startswith("sensor_")]
            try:
                nodes = [self._opc_client.get_node(info["node"]) for _, info in sensor_items]
                values = await self._opc_client.read_values(nodes)
                for (name, _), val in zip(sensor_items, values):
                    inputs[name] = bool(val)
                return inputs
            except Exception as exc:
                logger.warning("OPC UA 批量读取输入失败，降级逐点读取: %s", exc)
                await self._drop_opcua()
        for name in IO_MAP:
            if name.startswith("sensor_"):
                inputs[name] = await self.read_io(name)
        return inputs

    async def wait_for(self, io_name: str, target: bool, timeout: float = 5.0, interval: float = 0.1) -> bool:
        """轮询等待 I/O 到位；OPC UA 路径复用节点对象并减少每轮往返开销。

        返回 False 表示超时或通信失败（fail-closed，调用方必须把机械臂视为未到位）。
        """
        node = None
        if self._backend_type == "opcua" and self._opc_client is not None and io_name in IO_MAP:
            node = self._opc_client.get_node(IO_MAP[io_name]["node"])
        for _ in range(int(timeout / interval)):
            if node is not None and self._backend_type == "opcua" and self._opc_client is not None:
                try:
                    val = bool(await node.read_value())
                except Exception:
                    await self._drop_opcua()
                    return False
            else:
                val = await self.read_io(io_name)
            if val == target:
                return True
            await asyncio.sleep(interval)
        return False

    async def ensure_disconnected(self):
        for name in ["conveyor_entry", "conveyor_exit", "arm_move_x", "arm_move_z", "grab"]:
            try:
                await self.write_io(name, False)
            except Exception:
                pass

    def get_backend_info(self) -> dict:
        return {
            "backend": self._backend_type or "not connected",
            "has_opcua": HAS_ASYNCUA,
            "has_snap7": HAS_SNAP7,
            "has_simulated": True,
            "plc_ip": PLC_IP,
            "opcua_endpoint": OPCUA_ENDPOINT,
            "estop_reconfirmation_required": self._estop_reset_required,
            "estop_latch_persist_file": str(_ESTOP_LATCH_FILE) if _ESTOP_LATCH_FILE else "",
        }


# 全局单例
backend = RobotBackend()


# ── 后端类型 (自动选择) ──────────────────────────────────────────
# 'auto': 优先 OPC UA, 失败回退 snap7
# 'opcua': 强制 OPC UA
# 'snap7': 强制 snap7
# 'simulated': 内存模拟（无需硬件）
BACKEND = os.environ.get("ROBOT_BACKEND", "auto")

# ── FastMCP Server ──────────────────────────────────────────────────
mcp = FastMCP("robot-mcp")

# ── 认证 ───────────────────────────────────────────────
_AUTH_TOKEN = ""


def _default_auth_token() -> str:
    return os.environ.get("MCP_AUTH_TOKEN", "")


def _require_auth(token: str = "") -> None:
    """验证服务已配置认证令牌；未配置令牌时控制服务不可用（fail-closed）。

    令牌由 MCP 进程环境（MCP_AUTH_TOKEN）在启动时注入，工具不再把它作为
    参数在对话中传递（避免令牌进入工具 schema 与聊天日志）。stdio 传输的
    信任边界是本地进程本身；若调用方仍显式传入令牌，则仍按原值校验（兼容
    旧调用方）。
    """
    if not _AUTH_TOKEN:
        raise PermissionError("MCP_AUTH_TOKEN 未配置，服务不可用")
    if token and token != _AUTH_TOKEN:
        raise PermissionError("认证失败：无效的 auth token")


# ── 审计链 ───────────────────────────────────────────────
_robot_audit: AuditLogger | None = None


def _audit(operation: str, **kwargs) -> None:
    """记录 HMAC 链式防篡改审计日志（mcp_common.audit）。

    审计失败仅记录错误日志、不阻断控制（避免审计存储异常造成控制死锁）；
    生产环境应配置 AUDIT_HMAC_KEY 使审计链持久可验证。
    控制类写入的 fail-closed 前置门由 _begin_write_audit 单独强制。
    """
    global _robot_audit
    try:
        if _robot_audit is None:
            _robot_audit = AuditLogger(str(PROJECT_ROOT / "logs" / "robot_audit.log"))
        _robot_audit.log_operation(
            operation, actor=authenticated_actor(_AUTH_TOKEN, "robot"), **kwargs
        )
    except Exception as exc:
        logger.error("审计日志写入失败: %s", exc)


def _begin_write_audit(name: str, value: bool) -> str | None:
    """write_io 的审计前置门（fail-closed）：返回 None 放行，否则返回阻断原因。

    对齐 opcua-mcp/modbus-mcp 的 begin_control_operation 前置门模式：
    真实后端（opcua/snap7）执行器写入前必须先成功写入控制意图审计；
    审计链不可用（AuditStorageError/AuditConfigurationError 等）时拒绝
    执行写入，不能只靠事后 _audit 补记（fail-open）。模拟后端用于离线
    测试，不设此门（见 write_io 调用处的分支）。
    """
    global _robot_audit
    try:
        if _robot_audit is None:
            _robot_audit = AuditLogger(str(PROJECT_ROOT / "logs" / "robot_audit.log"))
        _robot_audit.begin_control_operation(
            "robot.write_io", name, authenticated_actor(_AUTH_TOKEN, "robot"),
            {"io": name, "value": bool(value)},
        )
        return None
    except Exception as exc:
        logger.error("审计前置门拒绝写入 %s=%s: %s", name, value, exc)
        return "审计链不可用，拒绝执行写入（fail-closed）"


# ── 人工确认（真实后端动作的一次性令牌） ───────────────
confirmation_service = ConfirmationService()


def _check_confirmation(operation: str, value: Any, confirmation_token: str) -> str | None:
    """真实后端动作要求一次性人工确认令牌；模拟模式放行。

    返回错误原因字符串，或 None 表示放行。令牌由已鉴权的人工会话经后端
    /confirmations 接口签发（机器人设备前缀支持属跨模块依赖，见 notes）。
    """
    mode = backend.backend_type or BACKEND
    if mode == "simulated":
        return None
    if not confirmation_token:
        return f"操作 {operation} 需要一次性人工确认令牌，拒绝执行"
    try:
        confirmation_service.consume(
            confirmation_token,
            operator=authenticated_actor(_AUTH_TOKEN, "robot"),
            target=operation,
            value=value,
            device_id=f"robot:{mode}",
        )
        return None
    except ConfirmationError as exc:
        return f"确认令牌无效或已使用: {exc}"


async def _safe_go_home() -> dict:
    """安全回位 — 仅在异常处理中使用，永不抛出异常。
    避免 go_home 失败时产生递归或级联异常。
    """
    try:
        await backend.write_io("grab", False)
        await asyncio.sleep(0.3)
        await backend.write_io("arm_move_z", False)
        await asyncio.sleep(0.5)
        await backend.write_io("arm_move_x", False)
        await asyncio.sleep(0.5)
        await backend.write_io("conveyor_entry", False)
        await backend.write_io("conveyor_exit", False)
        return {"status": "ok", "position": "home"}
    except Exception as exc:
        logger.error("安全回位失败: %s", exc)
        return {"status": "error", "error": "安全回位失败"}


# ═════════════════════════════════════════════════════════════════════
# MCP 工具
# ═════════════════════════════════════════════════════════════════════


@mcp.tool()
async def get_status() -> dict:
    """获取机器人当前状态：传感器值、急停、连接状态"""
    _require_auth()
    try:
        await backend.ensure_connected()
        conn = f"connected ({backend.backend_type})"
    except Exception as exc:
        logger.error("get_status 连接失败: %s", exc)
        conn = "error: 连接失败"

    sensors = await backend.read_all_inputs()
    position = "unknown"
    if sensors.get("sensor_moving_x") is True:
        position = "extended"
    elif sensors.get("sensor_moving_x") is False:
        position = "retracted"

    return {
        "connection": conn,
        "backend": backend.backend_type or "none",
        "plc_ip": PLC_IP,
        "scene": "Pick & Place (Basic)",
        "sensors": sensors,
        "estimated_position": position,
        "emergency_stop": sensors.get("sensor_estop") is not True,
        "emergency_stop_circuit_healthy": sensors.get("sensor_estop") is True,
        "estop_reconfirmation_required": backend.get_backend_info()["estop_reconfirmation_required"],
    }


@mcp.tool()
async def confirm_estop_recovery() -> dict:
    """人工确认急停安全回路恢复后，解除机器人动作闭锁。

    真实后端（OPC UA/snap7）还必须检测到 PLC 复位按钮（I0.6）已被人工按下，
    才允许解除闭锁——急停恢复必须由人工现场确认，不允许 AI 自行确认。
    """
    _require_auth()
    return await backend.confirm_estop_recovery()


@mcp.tool()
async def go_home() -> dict:
    """将机器人恢复到安全起始位置：X收回、Z升起、夹爪松开、传送带停止"""
    _require_auth()
    try:
        # 1. 松开夹爪
        result = await backend.write_io("grab", False)
        if result.get("status") != "ok":
            return result
        await asyncio.sleep(0.3)

        # 2. Z轴升起（假设上升是 False）
        result = await backend.write_io("arm_move_z", False)
        if result.get("status") != "ok":
            return result
        await asyncio.sleep(0.5)

        # 3. X轴收回（假设收回是 False）
        result = await backend.write_io("arm_move_x", False)
        if result.get("status") != "ok":
            return result
        await asyncio.sleep(0.5)

        # 4. 停止所有传送带
        result = await backend.write_io("conveyor_entry", False)
        if result.get("status") != "ok":
            return result
        result = await backend.write_io("conveyor_exit", False)
        if result.get("status") != "ok":
            return result

        _audit("robot.go_home", result="ok")
        return {"status": "ok", "position": "home", "message": "机器人已回到起始位置"}
    except Exception as exc:
        logger.error("go_home 执行异常: %s", exc)
        return {"status": "error", "error": "回位失败，请检查连接"}


@mcp.tool()
async def pick_item(confirmation_token: str = "") -> dict:
    """
    从入口传送带拾取物品。
    流程: 等待物料到位 → X伸出 → Z下降 → 夹爪闭合 → Z上升 → X收回

    Args:
        confirmation_token: 真实后端必须提供的一次性人工确认令牌（模拟模式免）
    """
    _require_auth()
    reason = _check_confirmation("pick_item", "pick", confirmation_token)
    if reason:
        return {"status": "error", "error": reason}
    return await _pick_item()


async def _pick_item() -> dict:
    """pick_item 的实现（不含认证/确认，供 run_pick_cycle 跨循环复用）"""
    try:
        # 检查急停
        reason = await backend.motion_permission_error()
        if reason:
            return {"status": "error", "error": reason}

        # 检查是否有物料已到位
        has_item = await backend.read_io("sensor_entry")
        if not has_item:
            # 尝试运行入口传送带送料
            await backend.write_io("conveyor_entry", True)
            arrived = await backend.wait_for("sensor_entry", True, timeout=3.0)
            if not arrived:
                await backend.write_io("conveyor_entry", False)
                return {"status": "error", "error": "入口无物料，等待超时。请确保场景已启动且入口有料"}

        # 停传送带
        await backend.write_io("conveyor_entry", False)
        await asyncio.sleep(0.2)

        # 1. X轴伸出
        await backend.write_io("arm_move_x", True)
        x_ok = await backend.wait_for("sensor_moving_x", True, timeout=3.0)
        if not x_ok:
            await _safe_go_home()
            return {"status": "error", "error": "X轴伸出超时，已回位"}
        await asyncio.sleep(0.3)

        # 2. Z轴下降
        await backend.write_io("arm_move_z", True)
        z_ok = await backend.wait_for("sensor_moving_z", True, timeout=3.0)
        if not z_ok:
            await _safe_go_home()
            return {"status": "error", "error": "Z轴下降超时，已回位"}
        await asyncio.sleep(0.3)

        # 3. 夹爪闭合
        await backend.write_io("grab", True)
        await asyncio.sleep(0.5)

        # 确认抓到
        detected = await backend.read_io("sensor_item_detected")
        if not detected:
            await backend.write_io("grab", False)
            await _safe_go_home()
            return {"status": "error", "error": "抓取失败（未检测到物料），已复位"}

        # 4. Z轴上升
        await backend.write_io("arm_move_z", False)
        z_up_ok = await backend.wait_for("sensor_moving_z", False, timeout=3.0)
        if not z_up_ok:
            await _safe_go_home()
            return {"status": "error", "error": "Z轴上升超时，已回位"}
        await asyncio.sleep(0.3)

        # 5. X轴收回
        await backend.write_io("arm_move_x", False)
        x_ret_ok = await backend.wait_for("sensor_moving_x", False, timeout=3.0)
        if not x_ret_ok:
            await _safe_go_home()
            return {"status": "error", "error": "X轴收回超时，已回位"}
        await asyncio.sleep(0.3)

        _audit("robot.pick_item", result="ok")
        return {"status": "ok", "action": "pick", "message": "物料已抓取，机械臂已收回"}
    except Exception as exc:
        logger.error("pick_item 执行异常: %s", exc)
        await _safe_go_home()
        return {"status": "error", "error": "抓取失败，已复位"}


@mcp.tool()
async def place_item(confirmation_token: str = "") -> dict:
    """
    将抓取的物料放置到出口传送带。
    流程: X伸出 → Z下降 → 夹爪松开 → Z上升 → X收回 → 启动出口传送带

    Args:
        confirmation_token: 真实后端必须提供的一次性人工确认令牌（模拟模式免）
    """
    _require_auth()
    reason = _check_confirmation("place_item", "place", confirmation_token)
    if reason:
        return {"status": "error", "error": reason}
    return await _place_item()


async def _place_item() -> dict:
    """place_item 的实现（不含认证/确认，供 run_pick_cycle 跨循环复用）"""
    try:
        reason = await backend.motion_permission_error()
        if reason:
            return {"status": "error", "error": reason}

        has_item = await backend.read_io("sensor_item_detected")
        if not has_item:
            return {"status": "error", "error": "夹爪中无物料，请先执行 pick_item()"}

        # 1. X轴伸出（到出口位置）
        await backend.write_io("arm_move_x", True)
        x_ok = await backend.wait_for("sensor_moving_x", True, timeout=3.0)
        if not x_ok:
            await _safe_go_home()
            return {"status": "error", "error": "X轴伸出超时，已回位"}
        await asyncio.sleep(0.3)

        # 2. Z轴下降
        await backend.write_io("arm_move_z", True)
        z_ok = await backend.wait_for("sensor_moving_z", True, timeout=3.0)
        if not z_ok:
            await _safe_go_home()
            return {"status": "error", "error": "Z轴下降超时，已回位"}
        await asyncio.sleep(0.3)

        # 3. 夹爪松开
        await backend.write_io("grab", False)
        await asyncio.sleep(0.5)

        # 4. Z轴上升
        await backend.write_io("arm_move_z", False)
        z_up_ok = await backend.wait_for("sensor_moving_z", False, timeout=3.0)
        if not z_up_ok:
            await _safe_go_home()
            return {"status": "error", "error": "Z轴上升超时，已回位"}
        await asyncio.sleep(0.3)

        # 5. X轴收回
        await backend.write_io("arm_move_x", False)
        x_ret_ok = await backend.wait_for("sensor_moving_x", False, timeout=3.0)
        if not x_ret_ok:
            await _safe_go_home()
            return {"status": "error", "error": "X轴收回超时，已回位"}
        await asyncio.sleep(0.3)

        # 6. 启动出口传送带运走物品
        await backend.write_io("conveyor_exit", True)
        await asyncio.sleep(2.0)
        await backend.write_io("conveyor_exit", False)

        _audit("robot.place_item", result="ok")
        return {"status": "ok", "action": "place", "message": "物料已放置到出口，已运走"}
    except Exception as exc:
        logger.error("place_item 执行异常: %s", exc)
        await _safe_go_home()
        return {"status": "error", "error": "放置失败，已复位"}


@mcp.tool()
async def move_arm_to(position: str, confirmation_token: str = "") -> dict:
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
      confirmation_token: 真实后端必须提供的一次性人工确认令牌（模拟模式免）
    """
    _require_auth()
    valid = ["home", "pick", "extend", "retract", "lower", "raise"]
    if position not in valid:
        return {"status": "error", "error": f"无效位置: {position}。可选: {', '.join(valid)}"}

    reason = _check_confirmation("move_arm_to", position, confirmation_token)
    if reason:
        return {"status": "error", "error": reason}

    try:
        if position in {"pick", "extend", "lower"}:
            reason = await backend.motion_permission_error()
            if reason:
                return {"status": "error", "error": reason}
        if position == "home":
            result = await backend.write_io("grab", False)
            if result.get("status") != "ok":
                return result
            await asyncio.sleep(0.2)
            result = await backend.write_io("arm_move_z", False)
            if result.get("status") != "ok":
                return result
            await asyncio.sleep(0.3)
            result = await backend.write_io("arm_move_x", False)
            if result.get("status") != "ok":
                return result
            await asyncio.sleep(0.3)

        elif position == "pick":
            await backend.write_io("arm_move_x", True)
            x_ok = await backend.wait_for("sensor_moving_x", True, timeout=3.0)
            if not x_ok:
                await _safe_go_home()
                return {"status": "error", "error": "X轴伸出超时，已回位"}
            await asyncio.sleep(0.2)
            await backend.write_io("arm_move_z", True)
            z_ok = await backend.wait_for("sensor_moving_z", True, timeout=3.0)
            if not z_ok:
                await _safe_go_home()
                return {"status": "error", "error": "Z轴下降超时，已回位"}
            await asyncio.sleep(0.2)
            await backend.write_io("grab", False)

        elif position == "extend":
            await backend.write_io("arm_move_x", True)
            x_ok = await backend.wait_for("sensor_moving_x", True, timeout=3.0)
            if not x_ok:
                await _safe_go_home()
                return {"status": "error", "error": "X轴伸出超时，已回位"}

        elif position == "retract":
            await backend.write_io("arm_move_x", False)
            x_ok = await backend.wait_for("sensor_moving_x", False, timeout=3.0)
            if not x_ok:
                await _safe_go_home()
                return {"status": "error", "error": "X轴收回超时，已回位"}

        elif position == "lower":
            await backend.write_io("arm_move_z", True)
            z_ok = await backend.wait_for("sensor_moving_z", True, timeout=3.0)
            if not z_ok:
                await _safe_go_home()
                return {"status": "error", "error": "Z轴下降超时，已回位"}

        elif position == "raise":
            await backend.write_io("arm_move_z", False)
            z_ok = await backend.wait_for("sensor_moving_z", False, timeout=3.0)
            if not z_ok:
                await _safe_go_home()
                return {"status": "error", "error": "Z轴上升超时，已回位"}

        _audit("robot.move_arm_to", position=position, result="ok")
        return {"status": "ok", "action": "move_to", "position": position,
                "message": f"机械臂已移动到 {position}"}
    except Exception as exc:
        logger.error("move_arm_to 执行异常: %s", exc)
        await _safe_go_home()
        return {"status": "error", "error": "移动失败，已复位"}


@mcp.tool()
async def run_pick_cycle(count: int = 1, confirmation_token: str = "") -> dict:
    """
    执行完整的 pick-and-place 循环（自动重复）。

    参数:
      count: 循环次数（1-10，默认1次）
      confirmation_token: 一次性人工确认令牌（真实后端强制，模拟模式免）。
        一个令牌即可授权整个循环序列；循环内每个动作仍受急停门禁独立保护。
    """
    _require_auth()
    count = max(1, min(count, 10))
    # 多循环自动运行前先做一次急停检查，避免在急停态下无谓启动
    reason = await backend.motion_permission_error()
    if reason:
        return {"status": "error", "error": reason}
    reason = _check_confirmation("run_pick_cycle", count, confirmation_token)
    if reason:
        return {"status": "error", "error": reason}
    results = []
    cycles_completed = 0
    try:
        for i in range(count):
            pick_result = await _pick_item()
            results.append({"cycle": i + 1, "step": "pick", "result": pick_result})
            if pick_result.get("status") != "ok":
                break
            place_result = await _place_item()
            results.append({"cycle": i + 1, "step": "place", "result": place_result})
            if place_result.get("status") != "ok":
                break
            # 每完成一轮完整的 pick+place 才计 1 次循环
            cycles_completed += 1

        _audit("robot.run_pick_cycle", total_requested=count, cycles_completed=cycles_completed)
        return {"status": "ok", "cycles_completed": cycles_completed,
                "total_requested": count, "details": results}
    except Exception as exc:
        logger.error("run_pick_cycle 执行异常: %s", exc)
        await _safe_go_home()
        return {"status": "error", "error": "循环执行失败，已回位", "partial_results": results}


@mcp.tool()
async def control_conveyor(direction: str = "stop", confirmation_token: str = "") -> dict:
    """
    控制传送带。

    参数:
      direction: "entry" → 入口传送带启动
                 "exit"  → 出口传送带启动
                 "stop"  → 全部停止
      confirmation_token: 启动传送带需要一次性人工确认令牌（模拟模式免）；
        停止是安全恢复动作，不需要确认。
    """
    _require_auth()
    try:
        if direction in {"entry", "exit"}:
            reason = await backend.motion_permission_error()
            if reason:
                return {"status": "error", "error": reason}
            reason = _check_confirmation("control_conveyor", direction, confirmation_token)
            if reason:
                return {"status": "error", "error": reason}
        if direction == "entry":
            result = await backend.write_io("conveyor_entry", True)
            if result.get("status") != "ok":
                return result
            result = await backend.write_io("conveyor_exit", False)
            if result.get("status") != "ok":
                return result
        elif direction == "exit":
            result = await backend.write_io("conveyor_entry", False)
            if result.get("status") != "ok":
                return result
            result = await backend.write_io("conveyor_exit", True)
            if result.get("status") != "ok":
                return result
        else:
            result = await backend.write_io("conveyor_entry", False)
            if result.get("status") != "ok":
                return result
            result = await backend.write_io("conveyor_exit", False)
            if result.get("status") != "ok":
                return result
        _audit("robot.control_conveyor", direction=direction, result="ok")
        return {"status": "ok", "direction": direction}
    except Exception as exc:
        logger.error("control_conveyor 执行异常: %s", exc)
        return {"status": "error", "error": "操作失败，请检查连接"}


# ═════════════════════════════════════════════════════════════════════
# CLI 入口
# ═════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # 认证令牌只从环境变量（MCP_AUTH_TOKEN）读取；不提供 --auth-token CLI
    # 参数，避免令牌暴露在进程命令行（ps/日志可见）。
    parser = argparse.ArgumentParser(description="Robot MCP Server — 工业机器人控制")
    parser.add_argument("--endpoint", default=None,
                        help=f"OPC UA 端点 (默认: {OPCUA_ENDPOINT})")
    parser.add_argument("--ip", default=None,
                        help=f"仅接受唯一隔离 PLC IP（默认: {PLC_IP}）")
    parser.add_argument("--backend", default=None,
                        choices=["auto", "opcua", "snap7", "simulated"],
                        help="通信后端 (默认: auto, 或从环境变量 ROBOT_BACKEND 读取)")
    parser.add_argument("--scene", default="Pick & Place (Basic)",
                        choices=["Pick & Place (Basic)", "Palletizer"],
                        help="Factory I/O 场景 (默认: Pick & Place (Basic))")
    args = parser.parse_args()
    _AUTH_TOKEN = _default_auth_token()
    if not _AUTH_TOKEN:
        raise SystemExit("Robot MCP 拒绝启动：必须配置 MCP_AUTH_TOKEN 环境变量")

    try:
        if args.endpoint:
            require_opcua_endpoint(args.endpoint)
        if args.ip:
            require_control_ip(args.ip)
    except TargetConfigurationError as exc:
        parser.error(str(exc))
    PLC_IP = get_control_target().plc_ip
    OPCUA_ENDPOINT = approved_opcua_endpoint()
    if args.backend:
        BACKEND = args.backend

    print(f"  Robot MCP Server starting...")
    print(f"  场景: {args.scene}")
    print(f"  PLC IP: {PLC_IP}")
    print(f"  后端: {BACKEND} (OPC UA={HAS_ASYNCUA}, snap7={HAS_SNAP7})")
    print(f"  机器人指令: get_status, go_home, pick_item, place_item, move_arm_to, control_conveyor, run_pick_cycle")
    mcp.run()
