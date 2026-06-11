# AI 接入 PLC 与工业机器人

> 构建生产级 AI Agent 系统，让 AI 通过自然语言直接监控、控制西门子 PLC、
> 三菱 PLC 和工业机器人，并具备自动生成西门子 PLC 梯形图 (LAD) / SCL 代码的能力。

**技术栈：** MCP + Python + C#/.NET + Docker + OPC UA / Modbus / MC 协议 + TIA Portal Openness

**版本：** TIA Portal V21 / PLCSIM Advanced V8.0 / Factory I/O

---

## 📦 实际项目结构

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
├── start_all.py                    # ⭐ 一键启动：PLCSIM + Factory I/O + TIA MCP
├── p3_flow.py                      # ⭐ P3 端到端：编译 + 下载 + FIO（TCP/IP）
├── run_gateway.py                  # 启动边缘网关
├── auto_full_pipeline.py           # 完整自动化流程脚本
├── check_progress.py               # 自动进度检测
├── docker-compose.yml              # InfluxDB + OpenPLC + Grafana
├── Makefile                        # 常用命令
├── .env                            # 环境变量（DEEPSEEK_API_KEY, TIA 路径等）
├── AGENTS.md                       # Agent 指令（补充 OpenCode.md）
├── claude.md                       # 项目总纲
└── OpenCode.md                     # 完整项目规则
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
pip install -r 环境/requirements.txt

# 4. 启动边缘网关（可选）
python run_gateway.py
```

### PLCSIM 全自动化

```python
from plcsim_api import restore_instance

# 从黄金备份恢复（无需 TIA Portal GUI）
instance = restore_instance(
    name="factoryio",
    golden_zip="D:\\backup\\factory_io1_golden.zip",
    storage_path="D:\\persist\\factoryio",
    ip="192.168.0.1",
    interface="tcpip",   # TCP/IP 模式（Factory I/O 要求）
)
# 实例已 RUN ✅
```

### 一键启动

```bash
python start_all.py              # 启动 PLCSIM + Factory I/O + TIA MCP
python start_all.py --tia-only   # 仅启动 TIA MCP Server
python start_all.py stop          # 停止所有
```

### 端到端下载

```bash
python p3_flow.py                 # 完整流程：PLCSIM → 编译 → 下载 → FIO
python p3_flow.py --download-only # 仅编译 + 下载
```

### 清理残留实例

```bash
python plcsim_api.py purge factoryio   # 强制清理残留实例数据
```

## 📊 当前进度

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
| **4** | 工业机器人 MCP (Pick & Place / OPC UA) | 🟡 开发中 |
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
- **`start_all.py`** 中实例名 `factory io1` 与 Factory I/O 要求的 `factoryio` 不同
- **CartGen**: 不支持并联分支（parallelElements），自保持用 Set/Reset 模式
- **三菱 MCP**: 无硬件测试环境
- **Pick & Place (Basic)**: 机械臂 I/O 时序需根据实际场景微调（延迟等待时间）
- **RoboDK 升级**: 后续阶段，当前聚焦 Factory I/O 内置场景

## 🔒 安全

- 所有写入操作需影子仿真验证（PLCSIM）
- 生产环境写入需人工确认
- 连续 3 次异常值自动熔断
- 审计日志不可篡改（只追加模式）
- 安全互锁规则配置（`safety/interlock-rules.yml`）

## 📚 参考

- [FastMCP](https://github.com/jlowin/fastmcp)
- [kukapay/opcua-mcp](https://github.com/kukapay/opcua-mcp)
- [Siemens TIA Portal Openness](https://support.industry.siemens.com)
- [Factory I/O](https://factoryio.com)
- [OpenPLC](https://openplcproject.com)

## License

MIT
