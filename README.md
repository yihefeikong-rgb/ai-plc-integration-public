# AI 接入 PLC 与工业机器人

> 让 Claude/Cursor/GPT 通过自然语言直接监控、控制西门子 PLC、三菱 PLC 和工业机器人，并自动生成西门子 PLC 代码。

## 快速开始

### 有西门子 S7-1200/1500（推荐）

```bash
# 1. 克隆项目
git clone <your-repo>
cd ai-plc-integration

# 2. 配置 PLC IP
# 编辑 mcp-servers/opcua-mcp/server.py 中的 PLC_URL

# 3. 启动 MCP Server
cd mcp-servers/opcua-mcp
python -m venv venv
source venv/bin/activate
pip install fastmcp asyncua
python server.py

# 4. 配置 Claude Desktop
# 编辑 ~/Library/Application Support/Claude/claude_desktop_config.json
# 添加 opcua-mcp server 路径

# 5. 重启 Claude，输入："读取当前温度"
```

### 无硬件（OpenPLC 仿真）

```bash
# 启动全栈仿真环境
docker-compose --profile simulation up -d

# 访问 http://localhost:8080 配置 OpenPLC
# 默认账号：openplc / openplc
```

## 项目结构

```
ai-plc-integration/
├── claude.md               # 项目总纲（给 Claude Code 的指令）
├── docker-compose.yml      # 全栈一键部署
├── docs/                   # 阶段文档
│   ├── phase-1-runtime.md      # 运行态基础
│   ├── phase-2-control-loop.md # AI控制闭环
│   ├── phase-3-tia-engineering.md # 西门子工程态
│   ├── phase-4-robot.md        # 工业机器人
│   └── phase-5-orchestration.md # 统一编排
├── mcp-servers/            # MCP 服务器
│   ├── opcua-mcp/          # 西门子 OPC UA
│   ├── mitsubishi-mcp/     # 三菱 MC 协议
│   ├── tia-mcp/            # TIA Portal Openness
│   └── robot-mcp/          # 工业机器人
├── edge-gateway/           # 边缘网关
└── plc-code-templates/     # AI 生成代码模板
```

## 五阶段计划

| 阶段 | 周期 | 目标 | 状态 |
|------|------|------|------|
| 1 | Week 1-2 | AI 读取 PLC 实时数据 | 🔲 |
| 2 | Week 3-4 | AI 控制闭环 + 本地 LLM | 🔲 |
| 3 | Week 5-7 | AI 生成西门子 SCL 代码 | 🔲 |
| 4 | Week 8 | 工业机器人接入 | 🔲 |
| 5 | Week 9-10 | 统一编排 + 安全加固 | 🔲 |

## 技术栈

- **MCP**: Model Context Protocol (FastMCP v3.1+)
- **PLC 通信**: OPC UA / Modbus TCP / 三菱 MC 协议
- **工程态**: TIA Portal Openness API (.NET)
- **本地 LLM**: Ollama + Qwen3-Coder / DeepSeek-Coder
- **数据**: InfluxDB + Grafana
- **部署**: Docker + Docker Compose

## 安全警告

⚠️ **生产环境必须遵守以下规则**：
1. AI 禁止直接操作急停回路
2. 所有写入操作需影子仿真验证
3. 生产环境写入需人工确认
4. 异常值连续 3 次自动熔断
5. 审计日志不可篡改

## 参考

- [kukapay/opcua-mcp](https://github.com/kukapay/opcua-mcp)
- [feelautom/tia-copilot-genai-bridge](https://github.com/feelautom/tia-copilot-genai-bridge)
- [pyri-project/pyri-core](https://github.com/pyri-project/pyri-core)
- [OpenPLC](https://openplcproject.com/)

## License

MIT
