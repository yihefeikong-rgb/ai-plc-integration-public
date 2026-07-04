# 项目状态 — AI 接入 PLC

> 生成日期：2026-06-23
> 扫描方式：只读目录与入口文件扫描，不读取业务代码内容
> 说明：基于当前仓库 `master` 分支的纯只读扫描结果

---

## 一、项目结构总览

```
AI 接入PLC/                          # 项目根
├── .ccb/                            # 协作层规则文件（Phase 1）
├── .plans/                          # Team OS 规划目录
│   └── ai-plc-integration/          # 项目规划（任务/进度/发现/决策/风险/架构）
│       ├── bridge/                  #   协作桥接层（state/task_packet/runner）
│       └── agents/                  #   角色定义（team-lead/developer/reviewer/documenter）
├── ai-plc-assistant/                # ⭐ 桌面应用（核心产品）
│   ├── backend/                     #   FastAPI 后端（33 端点，250 测试通过）
│   └── frontend/                    #   Electron + React + Vite（20 组件，零测试）
├── mcp-servers/                     # ⭐ MCP 服务器（8 个子模块）
│   ├── plc-mcp-bridge/              #   Siemens S7 运行态桥接（14 工具模块）
│   ├── tia-mcp/                     #   TIA Portal 工程态（36KB server.py + TiaWorker C#）
│   ├── opcua-mcp/                   #   OPC UA 协议（中成熟度）
│   ├── modbus-mcp/                  #   Modbus TCP（骨架）
│   ├── mitsubishi-mcp/              #   三菱 MC 协议（骨架）
│   ├── robot-mcp/                   #   工业机器人 Pick&Place（中成熟度）
│   ├── desktop-mcp/                 #   桌面控制（自实现 JSON-RPC）
│   └── tiacommander-mcp/            #   旧 TIA Commander（废弃）
├── orchestrator/                    # ⭐ 统一编排层（7 工作流，18 *.py 文件）
├── safety/                          # ⭐ 安全层（validator + shadow_simulator + audit）
├── edge-gateway/                    # 边缘网关（Docker + AI 控制闭环）
├── mcp_common/                      # MCP 公共库（config/audit/deepseek/tiaworker）
├── plc-code-templates/              # PLC 代码模板
│   └── siemens-scl/                 #   40+ SCL 模板 + _rules.md 规范
├── scripts/                         # 运维/冒烟脚本（11 个）
├── tests/                           # 根级测试（22 *.py 文件）
├── tools/                           # 诊断工具（3 个）
├── docs/                            # 技术文档（含 7 个 .lad 示例）
├── data/                            # 根级 data 目录（与 backend/data/ 有差异，待核查确认关系）
├── 软件/                            # 外部 C# 参考项目（含真实 API Key，已 .gitignore）
├── plc-programs/                    # 空目录
├── logs/                            # 运行日志
└── plc-mcp-kit/                     # Claude Code 插件/工具包
```

---

## 二、模块地图

### 2.1 核心应用层（ai-plc-assistant）

| 子模块 | 入口 | 说明 | 规模 |
|--------|------|------|------|
| backend | `main.py` (FastAPI) | 33 API 端点，11 routes | ~5KB main + 11 route 文件 |
| backend/generator | `generator/` | PLC 代码生成（SCL/XML/CSV/ASCII） | 6 文件 ~50KB |
| backend/knowledge | `knowledge/` | RAG 知识库（ChromaDB + chunker） | 3 文件 ~14KB |
| backend/llm | `llm/service.py` | LLM 服务（5 供应商） | 1 文件 ~7.4KB |
| backend/routes | `routes/` | API 路由（chat/generate/knowledge/search/等） | 11 文件 |
| backend/search | `search/` | 工程搜索（FTS5 + scanner） | 3 文件 |
| backend/storage | `storage/` | SQLite 持久化（conversations/projects/settings） | 3 文件 |
| backend/tests | `tests/` | 29 测试文件，250 测试通过 | 齐全 |

### 2.2 前端

| 子模块 | 说明 | 规模 | 测试 |
|--------|------|------|------|
| 组件 | 20 个 React 组件 | OrchestratorPanel 最大（44KB） | **零测试** |
| hooks | 6 个自定义 hooks | useConversation/useTabs/等 | 零测试 |
| 构建 | Vite + Tailwind + PostCSS | dist/ 输出 402KB JS + 20KB CSS | 无 vitest/jest 配置 |

### 2.3 MCP 服务器（8 个）

| 服务器 | 协议 | 成熟度 | 工具/文件数 | 安全关联 |
|--------|------|--------|-------------|---------|
| **plc-mcp-bridge** | FastMCP | **高** | 14 工具模块 | S7 读写/PLC 写入 |
| **tia-mcp** | FastMCP | **高(~98%)** | server.py 36KB + TiaWorker C# 141KB | TIA 工程写入 |
| opcua-mcp | FastMCP | 中 | 1 server + 1 safety | 运行态读写 |
| robot-mcp | FastMCP | 中 | 1 server 29KB + 测试 | 机器人急停 |
| desktop-mcp | 自实现 JSON-RPC | 中 | 1 server 16KB | 桌面控制 |
| modbus-mcp | FastMCP | 低（骨架） | 1 server 6.6KB | Modbus 通信 |
| mitsubishi-mcp | FastMCP | 低（骨架） | 1 server + 1 test | 无硬件环境 |
| tiacommander-mcp | — | 废弃 | — | — |

### 2.4 编排层（orchestrator）

| 文件/模块 | 用途 | 测试 |
|-----------|------|------|
| core.py | 工作流引擎（@workflow 装饰器 + Context） | 有 |
| mcp_client.py | 单服务器 MCP 客户端 | 有 |
| mcp_pool.py | 多服务器连接池 | 有 |
| safety_gate.py | 统一安全拦截点 | 有 |
| registry.py | 服务器/工具注册表 | 有 |
| api.py | FastAPI HTTP API（5 端点） | 有 |
| bootstrap.py | 启动引导 | 有 |
| workflows/ | 6 个工作流（s7_monitor/tia_pipeline/robot/等） | 有 |

### 2.5 安全层（safety）

| 文件 | 用途 | 状态 |
|------|------|------|
| validator.py | 互锁规则验证 | 高 |
| shadow_simulator.py | 影子仿真验证 | 高 |
| audit.py | HMAC 链式哈希审计日志 | 高 |
| interlock-rules.yml | 互锁规则定义（含机器人规则） | 已扩展 |

---

## 三、启动入口清单

### 3.1 桌面应用入口

| 入口 | 路径 | 说明 |
|------|------|------|
| 后端启动 | `ai-plc-assistant/start_backend.bat` | 启动 FastAPI（8005 端口） |
| 前端启动 | `ai-plc-assistant/start_frontend.bat` | 启动 Vite dev server |
| 一键启动（桌面） | `ai-plc-assistant/start.bat` | 前后端同时启动 |
| 全流程启动（根） | `start.bat` | 5 服务一键启动 |

### 3.2 MCP 服务器入口

| 入口 | 路径 |
|------|------|
| PLC MCP Bridge | `mcp-servers/plc-mcp-bridge/server.py` |
| TIA MCP | `mcp-servers/tia-mcp/server.py` |
| OPC UA MCP | `mcp-servers/opcua-mcp/server.py` |
| Robot MCP | `mcp-servers/robot-mcp/server.py` |
| 其他 MCP | `mcp-servers/{name}/server.py` |

### 3.3 流水线/脚本入口

| 入口 | 路径 | 说明 |
|------|------|------|
| P3 流水线 | `scripts/p3_flow.py` | 编译→下载→FIO 全流程 |
| 冒烟测试 | `scripts/e2e_smoke.py` | 端到端冒烟 |
| Demo 脚本 | `scripts/demo.py` | 固化演示 |
| 前置检查 | `scripts/preflight.py` | 环境前置检查 |
| 边缘网关 | `edge-gateway/src/app.py` | Docker AI 闭环 |

---

## 四、测试入口清单

### 4.1 活跃测试（68+ 测试文件 *.py）

| 测试目录 | *.py 文件数 | 测试用例数 | 状态 |
|----------|------------|-----------|------|
| `tests/`（根级） | 22（19 test_* + 3 辅助） | 待统计 | 通过 |
| `ai-plc-assistant/backend/tests/` | 29（26 test_* + 3 辅助） | 250 | 通过 |
| `orchestrator/tests/` | 18（16 test_* + 2 辅助） | 待统计 | 通过 |
| `mcp-servers/plc-mcp-bridge/tests/` | 5（4 test_* + conftest） | 待统计 | 通过 |
| `mcp-servers/robot-mcp/`（独立） | 2（test_*） | 待统计 | 通过 |
| `mcp-servers/mitsubishi-mcp/`（独立） | 1（test_*） | 待统计 | 通过 |

**说明**：文件数以目录内 `*.py` 文件总数计，括号内为 `test_*.py` 测试文件数。部分目录的测试用例数待后续补充。

### 4.2 归档测试（8 文件）

| 位置 | 说明 |
|------|------|
| `mcp-servers/tia-mcp/archived/test_*.py` | TIA 旧测试（CartGen/下载/布局等） |

### 4.3 C# 测试

| 位置 | 说明 |
|------|------|
| `TiaWorker.Tests/TiaWorker.Tests.csproj` | 91 测试通过（CommandValidator） |

### 4.4 测试缺口

| 缺口 | 说明 |
|------|------|
| **前端测试** | 零测试，无 vitest/jest 配置 |
| **E2E 测试** | 无 Playwright 集成 |
| **OPC UA MCP 测试** | 无独立测试文件 |
| **desktop-mcp 测试** | 无独立测试文件 |

---

## 五、风险边界说明

### 5.1 高风险区域（PLC/TIA/S7 写入）

| 区域 | 风险 | 当前防护 |
|------|------|---------|
| `safety/` | 安全链核心 | validator + shadow_sim + audit |
| `plc-mcp-bridge/s7_adapter.py` | S7 实时写入 | 安全互锁检查 |
| `plc-mcp-bridge/tools_s7.py` | S7 工具 | 安全层集成 |
| `tia-mcp/server.py` | TIA 工程写入 | scl_lint 静态校验 |
| `tia-mcp/TiaWorker/Program.cs` | TIA Openness 操作 | C# 层无独立安全校验 |
| `orchestrator/safety_gate.py` | 编排层安全门 | SafetyGate 拦截 |
| `scripts/p3_flow.py` | 全流水线下载 | 下载前编译校验 |

### 5.2 中风险区域

| 区域 | 风险 |
|------|------|
| `edge-gateway/` | AI 控制闭环，可能绕过安全层直接写入 |
| `robot-mcp/server.py` | 机器人控制含急停逻辑 |
| `mcp-servers/tia-mcp/archived/` | 旧脚本可能含有未迁移的逻辑依赖 |

### 5.3 低风险区域

| 区域 | 说明 |
|------|------|
| `ai-plc-assistant/backend/` | 纯 API 服务，不含 PLC 写入 |
| `ai-plc-assistant/frontend/` | 纯 UI，不含 PLC 操作 |
| `orchestrator/` | 已有 SafetyGate 拦截 |
| `docs/` | 纯文档 |
| `.plans/` | 纯规划文件 |
| `plc-code-templates/` | 纯模板文件 |

---

## 六、当前项目状态摘要

| 维度 | 评估 |
|------|------|
| 协作层（Phase 1-5.1B） | ✅ 完成（bridge/runner/受控自动化） |
| 编排层 | ✅ 7 工作流，18 *.py 文件，SafetyGate 集成 |
| 流水线修复 | ✅ 3 阻断 bug 修复，3 次 AI 重试 |
| SCL 质量防护 | ✅ 双轨（规范注入 + scl_lint） |
| 后端测试 | ✅ 250 测试通过 |
| 编排层测试 | ✅ 通过 |
| 冒烟/启动脚本 | ✅ 就绪 |
| **前端测试** | ❌ 零测试 |
| **E2E 测试** | ❌ 无 |
| **RBAC 安全网关** | ❌ 未开始 |
| **生产环境验证** | ⏳ 需真实 TIA V21 环境运行 |
