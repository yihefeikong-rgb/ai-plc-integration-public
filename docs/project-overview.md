# 项目概览

## 目标

构建 AI Agent 系统 + 本地工业自动化 AI 工作台，让 AI 通过自然语言：
- 监控西门子 PLC
- 控制 PLC（安全写入）
- 自动生成 PLC 代码
- 管理工业机器人工作流

## 技术栈

MCP + Python + C#/.NET + Electron + React + FastAPI + Docker + S7 协议 + TIA Portal Openness

## 项目结构

```
ai-plc-integration/
├── ai-plc-assistant/          # 桌面 AI 工作台（Electron+React+FastAPI）
│   ├── frontend/              # React + TailwindCSS + Lucide
│   ├── backend/               # FastAPI + ChromaDB + SQLite
│   └── start.bat              # 一键启动
├── orchestrator/              # 统一编排层（工作流引擎 + 安全拦截）
├── mcp-servers/               # MCP 服务器集合
│   ├── plc-mcp-bridge/        # S7 协议 + TIA 工程操作（65 工具）
│   ├── tia-mcp/               # TIA Portal Openness（TiaWorker C#）
│   ├── robot-mcp/             # 工业机器人控制
│   ├── opcua-mcp/             # OPC UA（备用）
│   ├── modbus-mcp/            # Modbus（骨架）
│   └── mitsubishi-mcp/        # 三菱 MC 协议（骨架）
├── edge-gateway/              # 边缘网关（S7+Modbus 双协议采集）
├── safety/                    # 安全模块（互锁/影子仿真/审计/熔断）
├── plc-code-templates/        # PLC 代码模板
├── tests/                     # 测试套件
├── scripts/                   # 运维脚本
└── docs/                      # 文档
```

## 架构

详见 `.plans/ai-plc-integration/docs/architecture.md`

## 安全约束

详见 `.plans/ai-plc-integration/docs/invariants.md`（12 条硬边界）

## 当前进度

详见 `.plans/ai-plc-integration/progress.md`