# 阶段 4：工业机器人接入 — Robot MCP Server

> 目标：让 AI 通过自然语言控制 Factory I/O 3D 工厂中的机器人，实现 pick-and-place 作业
> 后续升级：迁移到 RoboDK 专业机器人仿真器，支持 ABB / UR / FANUC 等真实机器人运动学

---

## 架构

```
用户/AI
  │ (MCP JSON-RPC)
  ▼
robot-mcp (FastMCP Server)
  │ (OPC UA)
  ▼
PLCSIM Advanced V8.0 (S7-1500 仿真)
  │ (TCP/IP)
  ▼
Factory I/O (3D 工厂场景 — Pick & Place / Palletizer)
```

### 通信链说明

| 层级 | 协议 | 组件 |
|:-----|:-----|:-----|
| AI → Robot | MCP (JSON-RPC) | `server.py` FastMCP |
| Robot → PLC | OPC UA | asyncua 库读写 PLCSIM 地址空间 |
| PLC → 工厂 | TCP/IP | S7-PLCSIM Advanced 驱动 |

---

## 场景选择

当前支持 Factory I/O 内置场景，无需额外安装：

| 场景 | 复杂度 | 机器人类型 | I/O 点数 | 推荐用途 |
|:-----|:------:|:----------:|:--------:|:---------|
| **Pick & Place (Basic)** | ⭐⭐ | 二轴气动 | 16I/16O | ⭐ P4 首选 — 简单可靠 |
| Palletizer | ⭐⭐⭐ | 三轴码垛 | 需确认 | 更复杂的码垛演示 |
| Pick & Place XYZ | ⭐⭐⭐ | 三轴伺服 | 需确认 | 更精确的定位演示 |
| Automated Warehouse | ⭐⭐⭐⭐ | 堆垛机 | 需确认 | 完整仓储物流 |

### Pick & Place (Basic) I/O 映射

**输入（传感器 → %I）**：
| 地址 | 信号名 | 说明 |
|:----:|:-------|:-----|
| I0.0 | Item at entry | 入口传感器 — 物料已到位 |
| I0.1 | Item at exit | 出口传感器 — 物料已送出 |
| I0.2 | Moving X | 机械臂X轴已伸出/缩回 |
| I0.3 | Moving Z | 机械臂Z轴已下降/上升 |
| I0.4 | Item detected | 夹爪夹到物料 |
| I0.5 | Start | 启动按钮 |
| I0.8 | Emergency stop | 急停信号 |

**输出（%Q → 执行器）**：
| 地址 | 信号名 | 说明 |
|:----:|:-------|:-----|
| Q0.0 | Entry conveyor | 入口传送带运行 |
| Q0.1 | Exit conveyor | 出口传送带运行 |
| Q0.2 | Move X | X轴伸出（True=伸出，False=缩回）|
| Q0.3 | Move Z | Z轴下降（True=下降，False=上升）|
| Q0.4 | Grab | 夹爪（True=抓紧，False=松开）|

---

## 快速开始

### 1. 前置条件

| 需求 | 说明 |
|:-----|:-----|
| PLCSIM Advanced V8.0 | 已恢复实例 `factoryio`，通信接口=TCP/IP |
| Factory I/O | 已安装，加载 Pick & Place (Basic) 场景 |
| Python 包 | `fastmcp`, `asyncua`（如未安装：`pip install asyncua`）|

### 2. 启动步骤

```bash
# 终端1: 启动机器人 MCP Server
cd ai-plc-integration
python mcp-servers/robot-mcp/server.py

# 终端2 (或通过 AI): 测试连接
# AI 调用 get_status() 查看机器人状态
```

### 3. 配置 Factory I/O

1. 打开 Factory I/O → `文件` → `加载场景` → 选 **Pick & Place (Basic)**
2. 按 `F4` 打开驱动窗口
3. 驱动类型选 **Siemens S7-PLCSIM**（Softbus 或 TCP/IP 均可）
4. 实例名填 `factoryio`（必须单引号）
5. 点击 **Connect**，确认状态变为绿色
6. 按 `空格` 启动场景

### 4. AI 控制示例

```
用户: "检查机器人状态"
AI → 调用 get_status()

用户: "把入口的物料搬到出口"
AI → 调用 pick_item() → place_item()

用户: "重复做5次 pick and place"
AI → 调用 run_pick_cycle(count=5)

用户: "回到起始位置"
AI → 调用 go_home()
```

---

## MCP 工具列表

| 工具 | 参数 | 功能 |
|:-----|:-----|:------|
| `get_status()` | 无 | 读取机器人全部传感器和连接状态 |
| `go_home()` | 无 | 复位到安全起始位置（X收回/Z升起/夹爪松开） |
| `pick_item()` | 无 | 从入口抓取物料：等待物料→X伸→Z降→夹紧→Z升→X收 |
| `place_item()` | 无 | 放置到出口：X伸→Z降→松开→Z升→X收→出口传送带走 |
| `move_arm_to(position)` | home/pick/extend/retract/lower/raise | 移动到指定姿态 |
| `run_pick_cycle(count)` | 1~10 | 自动重复 pick+place 循环 |
| `control_conveyor(direction)` | entry/exit/stop | 单独控制传送带 |

### 控制流程时序

```
pick() 时序:
  [等待]入口物料到位 ──→ [X伸出] ──→ [Z下降] ──→ [夹爪闭合]
                                                    ↓
                                           确认抓取到物料 ✓
                                                    ↓
                         [X收回] ←── [Z上升] ←── [夹爪保持]

place() 时序:
  [X伸出] ──→ [Z下降] ──→ [夹爪松开] ──→ [Z上升] ──→ [X收回]
                                                          ↓
                                              [出口传送带启动2s]
```

---

## 切换场景

### 使用 Palletizer（码垛机）

代码中已预留场景切换参数：

```bash
python mcp-servers/robot-mcp/server.py --scene Palletizer
```

切换场景时需修改 `IO_MAP` 中的 I/O 地址（需先通过 `fio_mapper.py` 获取场景 I/O 列表）。

### 使用 fio_mapper.py 获取任意场景 I/O

```bash
python mcp-servers/tia-mcp/fio_mapper.py
```

1. 在 Factory I/O 打开目标场景
2. F4 → 查看传感器/执行器列表
3. 交互式输入或从文件读取
4. 脚本生成 TIA Portal 标签表和 OB1 SCL 代码

---

## 升级到 RoboDK（后续阶段）

当 P4 基础功能跑通后，可用 RoboDK 替换 Factory I/O 的简单机器人仿真：

```python
# RoboDK Python API (极简示例)
from robodk import robodk
rdk = robodk.connect()
robot = rdk.Item('UR5')
robot.MoveJ([0, -90, 0, -90, 0, 0])  # 移动到目标位姿
```

**优势**：
- `pip install robodk` 即用
- 支持 ABB / UR / FANUC / KUKA 等 50+ 品牌机器人
- 原生支持 OPC UA 和 Modbus TCP

---

## 安全注意事项

- **急停优先**：所有机器人动作前检查 `%I0.8`（Emergency stop）
- **异常自动复位**：任何工具异常时自动调用 `go_home()` 回到安全位
- **OPC UA 连接中断**：工具会返回明确错误，不会产生不可控动作
- **建议**：第一次使用前在 Factory I/O 中手动操作，确认机械臂运动范围
