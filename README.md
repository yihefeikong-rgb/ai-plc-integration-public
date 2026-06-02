# AI 接入 PLC 与工业机器人

> 构建生产级 AI Agent 系统，让 AI 通过自然语言直接监控、控制西门子 PLC、
> 三菱 PLC 和工业机器人，并具备自动生成西门子 PLC 梯形图 (LAD) 代码的能力。

**技术栈：** MCP + Python + C#/.NET + OPC UA / Modbus / MC 协议 + TIA Portal Openness

---

## 📦 项目结构

```
ai-plc-integration/
├── mcp-servers/                    # MCP 服务器集合
│   ├── opcua-mcp/                  # OPC UA 运行时 MCP（西门子）
│   ├── modbus-mcp/                 # Modbus TCP MCP
│   ├── mitsubishi-mcp/             # 三菱 MC 协议 MCP（开发中）
│   └── tia-mcp/                    # ⭐ TIA Portal 工程态 MCP
│       ├── server.py               # FastMCP 服务（8 个工具）
│       ├── plcsim_api.py           # PLCSIM Advanced .NET API 封装
│       ├── config_loader.py        # 统一配置加载
│       ├── CartGen/                # JSON → SimaticML LAD 生成器 (C#)
│       ├── templates/              # 18 个 LAD 模板
│       ├── lad_creator.py          # LAD 创建器
│       └── gen_io_map.py           # IO 映射生成
├── edge-gateway/                   # 边缘网关（InfluxDB + 数据采集）
├── plc-code-templates/             # AI 生成 PLC 代码 Prompt 模板
├── safety/                         # 安全策略与审计
├── docs/                           # 技术文档
├── scripts/                        # 运维脚本
├── docker-compose.yml              # 全栈部署（InfluxDB + Grafana）
└── .env.example                    # 环境变量模板
```

## 🚀 快速开始

### 前置条件

| 需求 | 版本 | 用途 |
|------|------|------|
| Python 3.10+ | — | MCP Server + 工具链 |
| TIA Portal | V18 | 西门子工程态 |
| PLCSIM Advanced | V5.0 | S7-1500 仿真 |
| .NET SDK | 8.0 | CartGen LAD 生成器 |
| Factory I/O | 最新 | 3D 工厂可视化 |

### 环境设置

```bash
# 1. 克隆
git clone https://github.com/yihefeikong-rgb/ai-plc-integration
cd ai-plc-integration

# 2. 环境变量
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 3. 安装依赖
pip install -r requirements.txt  # 各 MCP 子目录下也有 requirements

# 4. 启动边缘网关（可选）
python run_gateway.py
```

### PLCSIM 全自动化

```python
from plcsim_api import restore_instance

# 从黄金备份恢复（无需 TIA Portal GUI）
instance = restore_instance(
    name="my_plc",
    golden_zip="D:\\backup\\factory_io1_golden.zip",
    storage_path="D:\\persist\\my_plc",
    ip="10.0.0.2",
    interface="tcpip",
)
# 实例已 RUN ✅
```

### 启动 TIA MCP Server

```bash
cd mcp-servers/tia-mcp
python server.py
# 暴露 8 个 MCP 工具：
#   list_devices / import_scl_file / compile_project
#   download_to_plcsim / generate_scl_code
#   generate_and_import / create_ladder_block / full_pipeline
```

### AI 生成梯形图

```bash
# 方式 1: 模板直接生成
dotnet run --project CartGen/CartGen.csproj -- templates/电机正反转.json

# 方式 2: AI + CartGen 流水线
python generate_custom.py  # 改 DESCRIPTION 即可
```

## 📊 当前进度

| 阶段 | 内容 | 状态 |
|------|------|:----:|
| **1** | OPC UA + Modbus 运行态基础 | ✅ 完成 |
| **2** | AI 控制闭环 + 安全互锁 + Grafana | ✅ 完成 |
| **3** | ⭐ TIA Portal 工程态 + LAD 生成 | 🟡 主要完成 |
| └─ | PLCSIM 首次下载限制突破 | ✅ |
| └─ | CartGen 18 模板全通过 | ✅ |
| └─ | golden.zip 归档/恢复 | ✅ |
| └─ | TCP/IP 虚拟网卡配置 | ❌ 待解决 |
| └─ | Factory I/O 自动连接 | ❌ 待解决 |
| **4** | 工业机器人（ABB/UR） | 🔲 |
| **5** | 统一编排 + 安全加固 | 🔲 |

## 🖥️ TIA MCP 工具链架构

```
自然语言描述
  ↓ DeepSeek API
LadderSpec JSON（IEC 61131-3）
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
| `download_to_plcsim` | 下载到 PLCSIM 仿真 |
| `generate_scl_code` | AI 生成 SCL 代码 |
| `generate_and_import` | 一站式 AI + 导入 |
| `create_ladder_block` | AI 生成梯形图 LAD 块 |
| `full_pipeline` | LAD + I/O 映射 + OB1 调用链 |

## 🚧 已知限制

- **首次下载**: 必须通过 TIA Portal GUI 完成一次（已解决：用 golden.zip）
- **TCP/IP 模式**: 需先安装 PLCSIM 虚拟网卡（VirtualSwitchMisconfigured）
- **CartGen**: 不支持并联分支（parallelElements），自保持用 Set/Reset 模式
- **三菱 MC 协议**: 暂无 MCP 实现（计划中）
- **工业机器人**: 待接入（计划阶段 4）

## 🔒 安全

- 所有写入操作需影子仿真验证（PLCSIM）
- 生产环境写入需人工确认
- 连续 3 次异常值自动熔断
- 审计日志不可篡改

## 📚 参考

- [FastMCP](https://github.com/jlowin/fastmcp)
- [kukapay/opcua-mcp](https://github.com/kukapay/opcua-mcp)
- [Siemens TIA Portal Openness](https://support.industry.siemens.com)
- [Factory I/O](https://factoryio.com)

## License

MIT
