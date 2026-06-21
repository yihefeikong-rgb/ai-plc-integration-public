# 系统架构 — AI 接入 PLC

> 这是 agent 可快速读取的架构真相。完整版见项目根 `ARCHITECTURE.md`。

---

## 4 层架构

```
Layer 1: 桌面应用层 — AI PLC Assistant
  Electron + React (11组件) ←→ FastAPI (33端点, 8005端口)
  ChromaDB (向量) + SQLite (对话/项目/搜索)

Layer 2: MCP 协议层
  plc-mcp-bridge (65 tools, S7+TIA+PLCSIM+FIO)
  tia-mcp/TiaWorker (C# TIA Openness)
  opcua-mcp / modbus-mcp / mitsubishi-mcp (骨架)

Layer 3: 工程+仿真层
  TIA Portal V21 + PLCSIM Advanced V8.0 + Factory I/O

Layer 4: 安全层 (贯穿)
  互锁规则(YAML) → 影子仿真 → 审计日志(HMAC链式哈希) → 写入熔断
```

## 关键数据流

```
对话: 用户输入 → SSE → RAG(ChromaDB) → LLM(DeepSeek) → 逐token渲染
生成: 自然语言 → LLM → LadderProgram → SCL/XML/CSV导出
搜索: 选择目录 → scanner → FTS5索引 → 搜索
写入: 请求 → 互锁检查 → 影子仿真 → 审计 → 实际写入 → 熔断监控
```

## 入口文件

| 入口 | 路径 |
|------|------|
| 桌面应用启动 | `ai-plc-assistant/start.bat` |
| 全流程启动 | `python start_all.py` |
| MCP 桥接 | `mcp-servers/plc-mcp-bridge/server.py` |
| TIA MCP | `mcp-servers/tia-mcp/server.py` |
| 边缘网关 | `python run_gateway.py` |
| 测试 | `D:/Python3/python.exe -m pytest tests/` |

## 数据库

| 数据库 | 路径 | 用途 |
|--------|------|------|
| SQLite | `ai-plc-assistant/backend/data/conversations.db` | 对话+消息 |
| SQLite | `ai-plc-assistant/backend/data/projects.db` | 项目管理 |
| SQLite | `ai-plc-assistant/backend/data/search_index.db` | FTS5 工程搜索 |
| ChromaDB | `ai-plc-assistant/backend/data/vector_db` | 知识库向量 |
| JSON | `ai-plc-assistant/backend/data/settings.json` | 应用设置 |