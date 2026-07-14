# AI 接入 PLC 与工业机器人

> 构建生产级 AI Agent 系统 + 本地工业自动化 AI 工作台。
> 让 AI 通过自然语言监控、控制西门子 PLC，并自动生成 SCL/LAD 代码。

**技术栈：** MCP + Python + C#/.NET + Electron + React + FastAPI + Docker

**版本：** TIA Portal V21 / PLCSIM Advanced V8.0

> **当前状态说明（2026-07-13）**：本仓库尚未在本次整改中完成真实 TIA、PLCSIM、PLC 或 Factory I/O 动态验收。所有控制目标必须由 `mcp-servers/tia-mcp/config.yaml` 的 `target` 节校验为 V21、`demo_V21.ap21`、`factoryio`、`192.168.0.110`；下方历史描述不能替代代码、配置和离线测试证据。

---

## AI PLC Assistant（桌面应用）

本地运行的工业自动化 AI 编程工作台，位于 `ai-plc-assistant/`。

**功能：** AI 聊天(DeepSeek/Claude/OpenAI/Kimi) | RAG 知识库 | PLC 工程搜索 | 梯形图生成 | SCL/XML/HMI 导出 | Prompt 模板 | 项目管理

**启动：** 双击 `ai-plc-assistant/start.bat`

**详细文档：** 见 [ai-plc-assistant/README.md](ai-plc-assistant/README.md)

---

## 当前可验证入口

| 入口 | 边界 |
|---|---|
| `D:/Python3/python.exe -m pytest` | 默认离线测试；不包含硬件、桌面或网络标记。 |
| `D:/Python3/python.exe scripts/preflight.py --json` | 只读环境检查，不证明下载成功或 PLC 可读。 |
| `start.bat` | 启动后端；其内嵌 orchestrator 是 MCP stdio 子进程的唯一生命周期所有者。 |
| `D:/Python3/python.exe scripts/p3_flow.py` | 可能改变仿真环境；仅在隔离目标和人工确认后使用。 |

## 历史结构草图（非命令来源）

> 本节保留为历史索引，部分文件名和完成度已过期；不存在的文件不能按此创建或执行。

```
ai-plc-integration/
├── mcp-servers/                    # MCP 服务器集合
│   ├── tia-mcp/                    # ⭐ TIA Portal 工程态 MCP（核心）
│   │   ├── server.py               # FastMCP 服务（8 个工具）
│   │   ├── plcsim_api.py           # PLCSIM Advanced .NET API 封装
│   │   ├── config_loader.py        # 统一配置加载（YAML + 环境变量）
│   │   ├── config.yaml             # 主配置文件
│   │   ├── CartGen/                # JSON → SimaticML LAD 生成器 (C# .NET 8)
│   │   ├── TiaWorker/              # TIA Openness 桥接 (C# .NET 4.8)
│   │   ├── tia_session.py          # TIA Portal Openness 会话管理（V21 模块化 DLL）
│   │   ├── lad_creator.py          # LAD 块创建器
│   │   ├── lad_creator.py / ladder_renderer.py  # 梯形图渲染
│   │   ├── generate_scl.py         # SCL 代码生成
│   │   ├── gen_io_map.py           # IO 映射生成
│   │   ├── templates/              # LAD 模板（18 个已验证）
│   │   ├── batch_gen_all.py        # 批量生成流水线
│   │   ├── download_to_plcsim.py / dl_plcsim_gui.py  # 下载到 PLCSIM
│   │   ├── test_dl_plcsim_gui.py / test_restore.py   # 测试
│   │   └── diagnose_download.py    # 下载诊断工具
│   ├── opcua-mcp/                  # OPC UA 运行时 MCP（西门子）
│   ├── modbus-mcp/                 # Modbus TCP MCP
│   └── mitsubishi-mcp/             # 三菱 MC 协议 MCP（✅ 已完成）
├── edge-gateway/                   # 边缘网关（InfluxDB + 数据采集 + AI 决策）
├── plc-code-templates/             # AI 生成 PLC 代码 Prompt 模板（SCL）
│   └── siemens-scl/                # 电机控制/传送带/PID/搅拌器/交通灯等
├── safety/                         # 安全策略与审计（互锁规则、审计日志）
├── mcp_common/                     # MCP 公共库（配置、审计、DeepSeek 客户端）
├── config/                         # 全局配置
├── docs/                           # 技术文档
├── scripts/                        # 运维脚本（自动启动、翻译、清理）
├── tools/                          # 诊断工具（IO 标签诊断）
├── tests/                          # 测试套件（pytest）
├── 环境/                           # 仿真环境（Python venv）
├── scripts/p3_flow.py              # P3 编排脚本（隔离目标下人工使用）
├── mcp-servers/plc-mcp-bridge/     # MCP 桥接服务器
├── docker-compose.yml              # InfluxDB + OpenPLC + Grafana
├── Makefile                        # 常用命令
├── .env                            # 环境变量（DEEPSEEK_API_KEY, TIA 路径等）
├── AGENTS.md                       # Agent 指令
├── claude.md                       # 项目总纲
```

## 🚀 快速开始

### 前置条件

| 需求 | 版本 | 用途 |
|------|------|------|
| Python 3.10+ | — | MCP Server + 工具链 |
| TIA Portal | V21 | 西门子工程态 |
| PLCSIM Advanced | V8.0 | S7-1500 仿真（向后兼容 V5.0+）|
| .NET SDK | 8.0 | CartGen LAD 生成器 |
| .NET Framework | 4.8 | TiaWorker 桥接 |
| Factory I/O | 最新 | 3D 工厂可视化 |

### 环境设置

```bash
# 1. 克隆
git clone https://github.com/yihefeikong-rgb/ai-plc-integration
cd ai-plc-integration

# 2. 环境变量
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 和 TIA 路径

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动本地服务（backend 内嵌 orchestrator 独占管理 stdio MCP 子进程）
start.bat
```

### 历史 PLCSIM 示例（禁止直接执行）

```python
from plcsim_api import restore_instance

# 从黄金备份恢复（无需 TIA Portal GUI）
# 历史示例已移除：旧的 IP/实例状态不能作为当前目标或已验收结论。
# 下载、恢复和 RUN 状态均需独立的隔离验收与回读证据。
```

### MCP 工具调用（通过 Claude Code）

PLC MCP Bridge 已作为 Claude Code 插件安装，AI 可直接调用 59 个工具：
- `plc_list_instances` — 列出 PLCSIM 实例
- `plc_compile_project` — 编译 TIA 项目
- `plc_download_project` — 下载到 PLCSIM
- `plc_run_pipeline` — 端到端流水线
- `s7_read` / `s7_write` — 实时读写 PLC 变量

### 端到端下载（受控、非默认）

```bash
D:/Python3/python.exe scripts/p3_flow.py                 # 可能恢复、下载、启动仿真
D:/Python3/python.exe scripts/p3_flow.py --download-only # 仍可能下载；需人工确认
```

### 清理残留实例

```bash
python plcsim_api.py purge factoryio   # 强制清理残留实例数据
```

## 📊 历史进度快照（非当前验收结论）

| 阶段 | 内容 | 状态 |
|------|------|:----:|
| **1** | OPC UA + Modbus 运行态基础 | ✅ 完成 |
| **2** | AI 控制闭环 + 安全互锁 + Grafana | ✅ 完成 |
| **3** | ⭐ TIA Portal 工程态 + LAD/SCL 生成 | ✅ 完成 |
| └─ | PLCSIM 首次下载限制突破（golden.zip 归档/恢复）| ✅ |
| └─ | CartGen 18 模板全通过 | ✅ |
| └─ | TIA Portal V21 升级适配 + DLL 拆分 | ✅ |
| └─ | TCP/IP 模式切换 + Factory I/O 连接 | ✅ |
| └─ | TiaWorker C# 桥接 + 端到端脚本 p3_flow.py | ✅ |
| **4** | 工业机器人 MCP (Pick & Place / OPC UA) | ⚪ 未开始（骨架） |
| └─ | robot-mcp 服务器 (7 工具) | ✅ 完成 |
| └─ | Pick & Place (Basic) 场景 I/O 映射 | ✅ 完成 |
| └─ | 安全复位/急停互锁/异常恢复 | ✅ 完成 |
| └─ | docs/phase-4-robot.md 文档 | ✅ 完成 |
| └─ | 集成到 start_all.py --with-robot | ✅ 完成 |
| └─ | 集成测试 tests/test_robot_mcp.py | ✅ 完成 |
| └─ | 真实硬件/PyRI/RoboDK 升级 | 🔲 待定 |
| **5** | 统一编排 + 安全加固 | 🔲 |

## 🖥️ TIA MCP 工具链架构

### 通信链
```
Claude/Cursor AI
  ↓ (MCP JSON-RPC)
server.py (FastMCP)
  ├── → 自然语言 → DeepSeek → SCL 代码 / LadderSpec JSON
  ├── → JSON 临时文件 → TiaWorker.exe(C# .NET 4.8) → TIA Openness DLL
  └── → CartGen(.NET 8) → SimaticML XML → 导入 TIA
```

### LAD 生成流水线
```
自然语言描述
  ↓ DeepSeek API
LadderSpec JSON（IEC 61131-3 规范）
  ↓ CartGen (.NET 8.0 / SimaticML)
SimaticML XML（TIA Portal 原生格式）
  ↓ _import_xml_into_tia()
TIA Portal 项目 → 编译 → PLCSIM 仿真 → Factory I/O 可视化
```

### 8 个 MCP 工具

| 工具 | 功能 |
|------|------|
| `list_devices` | 列出 TIA 项目中的 PLC 设备 |
| `import_scl_file` | 导入 SCL 源代码到 TIA 项目 |
| `compile_project` | 编译 TIA 项目 |
| `download_to_plcsim` | 下载到 PLCSIM 仿真器 |
| `generate_scl_code` | AI 生成 SCL 代码 |
| `generate_and_import` | 一站式 AI 生成 + 导入 |
| `create_ladder_block` | AI 生成梯形图 LAD 块 |
| `full_pipeline` | 全流水线：LAD + I/O 映射 + OB1 调用链 |

## 🧩 已知问题

- **TCP/IP 模式**: 需先安装 PLCSIM 虚拟网卡（VirtualSwitchMisconfigured）
- **ConveyorControl FB501**: 已在 TIA 项目中但未在 OB1 中调用
- `start_all.py` 不存在；请使用“当前可验证入口”而非历史脚本名
- **CartGen**: 不支持并联分支（parallelElements），自保持用 Set/Reset 模式
- **三菱 MCP**: 无硬件测试环境
- **Pick & Place (Basic)**: 机械臂 I/O 时序需根据实际场景微调（延迟等待时间）
- **RoboDK 升级**: 后续阶段，当前聚焦 Factory I/O 内置场景

## 🔒 安全

- 所有写入操作需影子仿真验证（PLCSIM）
- 生产环境写入需双人确认（操作人 + 确认人）
- 连续 3 次异常值自动熔断（需双人确认后人工重置）
- 审计日志不可篡改（HMAC 链式哈希 + 只追加模式）
- 安全互锁规则配置（`safety/interlock-rules.yml`）

### MCP 服务器认证

所有 MCP 服务器（tia-mcp / opcua-mcp / modbus-mcp / mitsubishi-mcp / desktop-mcp / robot-mcp）均通过 `MCP_AUTH_TOKEN` 环境变量启用认证：

```bash
# .env 或环境变量中设置
export MCP_AUTH_TOKEN="your-secret-token"
```

未设置此环境变量时，MCP 服务器将**拒绝所有请求**（默认拒绝策略）。部署前必须设置此变量。`plc-mcp-bridge` 作为内部桥接服务器不在此列。

## 📚 参考

- [FastMCP](https://github.com/jlowin/fastmcp)
- [kukapay/opcua-mcp](https://github.com/kukapay/opcua-mcp)
- [Siemens TIA Portal Openness](https://support.industry.siemens.com)
- [Factory I/O](https://factoryio.com)
- [OpenPLC](https://openplcproject.com)

## License

MIT
