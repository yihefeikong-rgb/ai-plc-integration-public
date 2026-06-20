# PROJECT HANDOVER — AI 接入 PLC

> **交接时间**: 2026-06-18
> **交接人**: Claude Code
> **接收方**: Reasonix（新 AI 工程师）
> **项目状态**: V1.0 功能基本完成，知识库生态持续扩展中

---

## 1. 项目概览

### 项目名称
**AI 接入 PLC** (AI-PLC Integration)

### 项目目标
构建 AI Agent 系统 + 本地工业自动化 AI 工作台，让 AI 通过自然语言监控、控制西门子 PLC，并自动生成 PLC 代码。

### 当前完成度

| 模块 | 完成度 | 说明 |
|------|--------|------|
| S7 运行态读写 | 100% | python-snap7 协议层 |
| AI 控制闭环 + 安全链 | 100% | 互锁/影子仿真/审计/熔断 |
| TIA 工程态 (TiaWorker) | 90% | C# TIA Openness + PLCSIM |
| AI PLC Assistant 桌面应用 | 95% | V1.0 功能完整 |
| 知识库生态 (SCL模板) | 80% | 20+ SCL模板，持续扩充 |
| Prompt 模板系统 | 100% | 22 个模板（16 Prompt + 6 新SCL） |
| 工业机器人 | 0% | 未开始 |
| 统一编排 | 0% | 未开始 |

### 已实现功能

1. **AI PLC Assistant 桌面应用** — Electron + React + FastAPI
   - AI 对话（SSE 流式 + RAG 增强）
   - 梯形图生成（自然语言 → 结构化 → SCL/XML/CSV/HMI 导出）
   - 代码解析、IO 表生成、故障诊断 3 个专用工作台
   - 知识库（ChromaDB 向量检索，PDF/DOCX/TXT 导入）
   - PLC 工程搜索（SQLite FTS5 全文索引，XML/SCL/CSV/AWL 解析）
   - Prompt 模板系统（22 个模板，分类管理）
   - 项目管理（CRUD + .ap18 导入）
   - 5 模型供应商（DeepSeek/OpenAI/Kimi/Claude/自定义）
   - 流式输出 SSE
   - 模型自动切换（主模型失败 → 逐个尝试备选）
   - 对话持久化（SQLite 多会话）
   - 代码导出（SCL/PLCopen XML/CSV/HMI/报警/JSON）
   - SCL 代码模板弹窗（20+ 文件）
   - 梯形图 LAD 模板弹窗（20+ JSON 模板）
   - 侧栏分组折叠（基础/进阶/行业）
   - 知识库文档列表 + 删除 + 统计
   - 设置面板（API Key 遮盖/测试连接）

2. **PLC MCP 服务器** — MCP 协议封装西门子 PLC 操作
   - 65 个工具（S7 读写/TIA 工程/PLCSIM/Factory I/O）
   - S7 协议读写（DB/M/I/O）
   - TIA 工程操作（创建/删除/编译/下载块）
   - 标签表管理（CRUD + 冲突检测）
   - UDT/DB 管理
   - 监控表管理
   - PLCSIM 生命周期管理
   - Factory I/O 联动
   - Pipeline 一键部署（Golden → 编译 → 下载 → 启动）

3. **安全模块** — 工业安全防护层
   - 互锁验证（interlock-rules.yml）
   - 影子仿真（shadow_simulator.py）
   - 审计日志（链式哈希）
   - 写入校验（validator.py）

4. **TIA Worker** — C# TIA Portal Openness 集成
   - SCL 代码生成并写入 TIA Portal
   - 梯形图 LAD 生成（20+ JSON 模板 → TIA 块）
   - PLCSIM 管理（创建/启动/停止/切换 TCP/IP）
   - PLCopen XML 导入
   - 下载/编译/归档
   - Golden backup/restore

5. **PLC 代码模板**
   - SCL 模板: 22 个（含中文名 停车场/电梯/HVAC）
   - LAD 模板: 20 个 JSON（从星三角到立体仓库）
   - PLCopen XML: 2 个标准示例

### 未实现功能

| 功能 | 优先级 | 原因 |
|------|--------|------|
| 梯形图 SVG 可视化 | P1 | 核心功能缺陷，需要图形化展示 |
| Electron 打包验证 | P1 | 配置已完成但未实际测试 |
| 前端 E2E 测试 | P2 | Playwright 未配置 |
| 中文分词优化 | P2 | FTS5 LIKE 搜索准确率低 |
| 多轮 RAG 对话记忆 | P2 | 支持追问式检索 |
| 代码 Diff 视图 | P2 | 查看 AI 修改前后差异 |
| HMI 变量导入导出 | P2 | 工程流转闭环 |
| 多语言界面 | P3 | 海外用户支持 |
| TIA Openness 集成 | V2.0 | 安全链未成熟 |
| AI 直连 PLC 运行态 | V2.0 | 安全链未成熟 |
| RBAC 权限控制 | V2.0 | 多用户场景 |

### 已知问题

1. **RAG 中文检索准确率低** — all-MiniLM-L6-v2 对中文支持差，计划换 BAAI/bge-m3
2. **工程搜索中文不分词** — FTS5 unicode61 对 CJK 不处理，后备 LIKE 查询性能低
3. **梯形图→SCL 转换弱** — `_ladder_to_scl()` 只能处理简单串联触点
4. **LLM 回退提示不明显** — 模型切换只在 warn log 显示，用户看不到
5. **前后端版本不一致** — 前端 package.json=1.0.0，后端 main.py=0.1.0
6. **零测试覆盖率**（AI PLC Assistant）— 父项目有 10+ 测试但子应用没有
7. **ChromDB 路径混淆** — 项目用 data/vector_db 而非 data/chroma_db

---

## 2. 技术架构

### 前端技术栈
- **Electron 31** + **React 18** + **Vite 5** + **TailwindCSS 3.4**
- Lucide React 图标
- react-markdown 渲染 AI 回复
- 无 TypeScript（纯 JSX），无状态管理库（Custom Hooks）

### 后端技术栈
- **Python 3.13** + **FastAPI 0.111** + **Uvicorn**
- ChromaDB 0.5（向量检索）
- SQLite 3（WAL 模式，FTS5 全文索引）
- OpenAI SDK（OpenAI 兼容）+ Anthropic SDK（Claude）
- PyMuPDF（PDF 解析）+ python-docx（DOCX 解析）
- MCP Python SDK（MCP 服务器）

### 数据库结构

| 数据库 | 用途 | 路径 |
|--------|------|------|
| ChromaDB | 向量检索（知识库） | data/vector_db/ |
| conversations.db | 对话历史 | data/conversations.db |
| projects.db | 项目管理 | data/projects.db |
| search_index.db | 工程全文搜索 | data/search_index.db |
| settings.json | 应用配置 | data/settings.json |

### API 结构（33 端点）

| 前缀 | 端点数 | 说明 |
|------|--------|------|
| `/api/chat` | 2 | 非流式 + SSE 流式 |
| `/api/models` | 2 | 模型列表 + 详情 |
| `/api/knowledge` | 5 | 知识库 CRUD |
| `/api/search` | 5 | 工程全文搜索 |
| `/api/generate` | 6 | 梯形图/SCL/XML/导出 |
| `/api/prompts` | 7 | Prompt 模板 CRUD |
| `/api/conversations` | 7 | 对话历史 |
| `/api/projects` | 7 | 项目管理 |
| `/api/settings` | 4 | 设置读写 |
| `/api/health` | 1 | 健康检查 |

### 目录结构说明

```
ai-plc-integration/
├── ai-plc-assistant/          # ⭐ 主桌面应用
│   ├── frontend/              # React + Electron 前端
│   │   ├── src/               # JSX 源码
│   │   │   ├── App.jsx        # 主编排层（115行，5个custom hooks）
│   │   │   ├── api.js         # API 通信（fetch + SSE）
│   │   │   └── components/    # 11个组件
│   │   ├── electron/          # Electron 主进程
│   │   └── package.json       # 含 electron-builder 打包配置
│   ├── backend/               # FastAPI 后端
│   │   ├── main.py            # 入口 + 路由注册
│   │   ├── config.py          # Pydantic Settings
│   │   ├── routes/            # 9 个路由模块
│   │   ├── llm/               # LLM 调用层（5模型 + 自动切换 + 流式）
│   │   ├── knowledge/         # 知识库引擎（ChromaDB）
│   │   ├── search/            # 工程搜索（FTS5）
│   │   ├── generator/         # 代码生成器（SCL/XML/CSV）
│   │   ├── storage/           # 持久化层（SQLite + JSON）
│   │   └── data/              # 数据文件
│   └── start.bat              # 一键启动
│
├── mcp-servers/               # MCP 服务器集合
│   ├── plc-mcp-bridge/        # S7 + TIA（65 工具，主力）
│   ├── tia-mcp/               # TIA Worker（C# Openness + PLCSIM）
│   │   ├── TiaWorker/         # C# TIA Openness
│   │   ├── CartGen/           # C# 料车生成器
│   │   └── templates/         # 20个JSON梯形图模板
│   ├── tiacommander-mcp/      # 闭源，已过期
│   ├── opcua-mcp/             # OPC UA（骨架）
│   ├── modbus-mcp/            # Modbus（骨架）
│   ├── mitsubishi-mcp/        # 三菱 MC 协议（骨架）
│   └── robot-mcp/             # 机器人（骨架）
│
├── safety/                    # 安全模块
├── plc-code-templates/        # SCL + XML 代码模板
├── tests/                     # 父项目测试（10+）
├── scripts/                   # 运维脚本
├── docs/                      # 阶段文档
├── mcp_common/                # MCP 公共库
└── tools/                     # 辅助工具
```

---

## 3. 当前开发状态

### 最近完成的工作（按时间倒序）

1. **SCL 模板中文标题 + 知识库文件名修复**（commit 934daca）
   - 6 个新 SCL 模板（泵站/冷却塔/包装机/SBR/CIP/PID）
   - API 返回 title 字段，前端显示中文名
   - 文件名导入时传递原始文件名修复 tmp_xxx 问题

2. **SCL 代码模板弹窗**（commit 99ac49d）
   - 新建 CodeTemplateModal.jsx
   - 后端 /api/knowledge/code-templates/{name} 端点
   - 前端 api.js 新增 listCodeTemplates/getCodeTemplateContent
   - App.jsx 接入弹窗

3. **知识库分组折叠**（commit 99ac49d）
   - Sidebar.jsx DocGroup defaultOpen=false
   - 按 01-03/04-10/11-99 三级分组

4. **侧栏模板标签改名**（commit df07a26）
   - 提示词模板 / SCL 代码模板

5. **模板库扩充**（commit 1d316cf）
   - 16 个 Prompt 模板 + 6 个 SCL 模板
   - .gitignore 放开 data/*.json

### 当前卡住的问题

1. **梯形图模板格式兼容** — Deep Research 找到的资源是图片/PDF，不是 JSON 格式，需手写 JSON 模板
2. **电梯/停车场/HVAC 模板** — Deep Research 两次 Exa API 断流导致未完成
3. **缺少自动化测试** — AI PLC Assistant 无 pytest/vitest/Playwright 测试
4. **SVG 梯形图可视化** — 数据结构已有（LadderProgram），但缺少图形渲染层

### 下一步（按优先级）

1. **P0: 保存当前对话** — 生成所有交接文档后，用 /save-session 保存上下文
2. **P1: 梯形图 SVG 可视化** — 根据 structured.networks 渲染 SVG
3. **P1: Electron 打包验证** — npm run dist 实际测试
4. **P1: 基础测试覆盖** — pytest 后端 API 测试
5. **P2: 电梯/停车场/HVAC SCL 模板** — 手写补全
6. **P2: 梯形图 JSON 模板** — 手写更多场景

---

## 4. AI 上下文知识库

> ⚠️ **最重要部分**：以下信息不在代码中，但在上下文中积累的经验

### 设计思路

#### 4.1 "AI 辅助人，不替代人"
- 所有 AI 生成的代码需要工程师审核确认
- AI 定位是"加速器"而非"自动驾驶"
- V1.0 刻意不做 Agent（不直接连接运行态 PLC）
- 理由：进入工业安全责任领域后，停机/损坏风险无法接受

#### 4.2 架构选型逻辑

| 选型 | 核心原因 | 放弃的方案 |
|------|---------|-----------|
| FastAPI | 原生 async + SSE 流式 + Python AI 生态 | Django（太重）、Flask（无 async） |
| Electron | 本地文件系统访问（工厂内网刚需） | Tauri（与 Python AI 不兼容）、纯 Web |
| ChromaDB | 零依赖、本地持久化、纯 Python | Pinecone（需云）、FAISS（无元数据过滤） |
| SQLite | 零配置、单用户够用 | PostgreSQL（维护成本）、MongoDB（不需要） |
| DeepSeek 主力 | 性价比高、中文强、PLC 代码质量好 | OpenAI（中国不稳定）、本地模型（推理弱） |
| SSE 流式 | 单向足够、HTTP 简单、FastAPI 原生支持 | WebSocket（过度设计） |
| Custom Hooks | 最轻量状态拆分、无新依赖 | Redux（过度设计）、Context（仅一层消费者） |

#### 4.3 放弃过的方案

1. **TiaCommander**（闭源 MCP 服务器）
   - 原因：闭源 + Beta 已过期（2026-06-19）
   - 替代：自研 TiaWorker（C# TIA Openness）
   - 状态：TiaWorker 已覆盖 90% 功能

2. **FAISS 替代 ChromaDB**
   - 原因：FAISS 没有内置持久化和元数据过滤
   - 结果：坚持用 ChromaDB

3. **Agent 模式（V1.0 不做）**
   - 原因：安全链不成熟、测试覆盖刚建立
   - 重新评估条件：115+ 测试持续绿灯、实机验证、3-5 真实用户反馈

4. **Ollama 本地模型**
   - 原因：7B/13B 模型 PLC 代码生成质量不够
   - 结果：坚持用云 API（DeepSeek 主力）

#### 4.4 已验证有效的方法

1. **DeepSeek V4 生成 PLC 代码质量好** — 中文能力强，SCL 语法准确
2. **ChromaDB + 500字块 + 100字重叠** — 知识库检索效果可接受
3. **模型自动切换** — 主模型失败时逐个尝试备选，对用户透明
4. **PLC 系统 Prompt** — 内置匈牙利命名法、安全编程原则，显著提高代码质量
5. **SSE 流式** — 逐 token 渲染，用户体验好，实现简单

#### 4.5 已验证失败的方法

1. **多次删 data/chroma_db** — 实际路径是 data/vector_db，删错目录
2. **Exa API 网络断流** — 两次 Deep Research 中断，楼宇/HVAC 方向未完成
3. **all-MiniLM-L6-v2 中文检索** — 中文工业文档准确率低
4. **FTS5 LIKE 中文查询** — 性能差、准确率低
5. **`_ladder_to_scl()` 后处理** — 只能处理最简情况，SCL 应由 LLM 直接生成

#### 4.6 关键路径与数据流

**SSE 流式对话**（最核心路径）：
```
用户输入 → useConversation.handleSend()
  → streamChat() → POST /api/chat/stream
  → 后端 RAG 检索 ChromaDB
  → 注入 system prompt + RAG 上下文
  → LLM chat_stream() → 逐 token yield
  → SSE: data: {"token": "..."} × N
  → 前端 ReadableStream 拼接 → ReactMarkdown 渲染
  → 对话持久化 SQLite
```

**知识库导入**：
```
上传 PDF/DOCX/TXT
  → POST /api/knowledge/import
  → parsers.py 解析为纯文本
  → chunker.py 分块（500字/块，100字重叠）
  → ChromaDB.add() → all-MiniLM-L6-v2 嵌入
```

**梯形图生成**：
```
自然语言输入
  → LLM 生成结构化 LadderProgram
  → generator/workflow.py 解析
  → 可选导出：SCL / PLCopen XML / CSV 标签表 / HMI / 报警 / JSON
```

---

## 5. 关键文件清单

### 必须阅读

| 文件 | 作用 |
|------|------|
| `docs/phase-1-runtime.md` | S7 协议层设计文档 |
| `docs/phase-2-control-loop.md` | AI 控制闭环 + 安全链设计 |
| `docs/phase-3-tia-engineering.md` | TIA 工程态设计 |
| `safety/interlock-rules.yml` | 安全互锁规则定义 |
| `safety/shadow_simulator.py` | 影子仿真引擎 |
| `mcp-servers/plc-mcp-bridge/server.py` | plc-mcp-bridge 入口（65 工具） |
| `mcp-servers/tia-mcp/server.py` | TIA Worker MCP 入口 |
| `mcp-servers/tia-mcp/TiaWorker/Program.cs` | C# TIA Openness 核心 |
| `mcp_common/config.py` | 全局配置加载 |
| `scripts/p3_flow.py` | P3 一键流水线 |

### AI PLC Assistant 关键文件

| 文件路径 | 作用 | 必须读 |
|----------|------|--------|
| `ai-plc-assistant/backend/main.py` | FastAPI 入口，路由注册 + 全局异常处理 | 是 |
| `ai-plc-assistant/backend/config.py` | Pydantic 设置 + .env 加载 | 是 |
| `ai-plc-assistant/backend/llm/service.py` | LLM 调用层（5 模型 + 自动切换 + 流式） | 是 |
| `ai-plc-assistant/backend/routes/chat.py` | AI 对话 + RAG 注入 | 是 |
| `ai-plc-assistant/backend/routes/knowledge.py` | 知识库 API + 代码模板端点 | 是 |
| `ai-plc-assistant/backend/routes/generate.py` | 梯形图生成 + 代码导出 | 是 |
| `ai-plc-assistant/backend/knowledge/engine.py` | ChromaDB 引擎封装 | 是 |
| `ai-plc-assistant/backend/knowledge/parsers.py` | PDF/DOCX/TXT 解析 | 是 |
| `ai-plc-assistant/backend/knowledge/chunker.py` | 文本分块器 | 是 |
| `ai-plc-assistant/backend/search/indexer.py` | SQLite FTS5 索引 | 是 |
| `ai-plc-assistant/backend/generator/__init__.py` | LadderProgram 数据模型 | 是 |
| `ai-plc-assistant/backend/generator/workflow.py` | 生成工作流 | 是 |
| `ai-plc-assistant/backend/storage/conversations.py` | 对话持久化 | 否 |
| `ai-plc-assistant/backend/storage/app_settings.py` | 设置 JSON 存储 | 否 |
| `ai-plc-assistant/backend/data/prompts.json` | 22 个 Prompt 模板 | 是（读模板内容） |
| `ai-plc-assistant/frontend/src/App.jsx` | 前端主编排层 | 是 |
| `ai-plc-assistant/frontend/src/api.js` | API 通信层 | 是 |
| `ai-plc-assistant/frontend/src/components/ChatArea.jsx` | AI 聊天组件 | 是 |
| `ai-plc-assistant/frontend/src/components/Sidebar.jsx` | 侧栏导航 | 是 |
| `ai-plc-assistant/frontend/src/components/SettingsPanel.jsx` | 设置页面 | 否 |
| `ai-plc-assistant/frontend/src/components/CodeTemplateModal.jsx` | SCL 代码模板弹窗 | 否 |
| `ai-plc-assistant/frontend/src/components/LadderTemplateModal.jsx` | 梯形图模板弹窗 | 否 |
| `ai-plc-assistant/start.bat` | 一键启动脚本 | 是 |
| `ai-plc-assistant/ARCHITECTURE.md` | 系统架构文档 | 是 |
| `ai-plc-assistant/DECISIONS.md` | 技术决策记录 | 是 |
| `ai-plc-assistant/PROJECT_STATUS.md` | 项目状态报告 | 是 |

---

## 6. 开发路线图

### Phase 1 — V1.0 正式版（当前）

**目标**: 功能完整的桌面 AI PLC 助手，可交付使用

**任务**:
- [ ] 梯形图 SVG 可视化（核心功能缺陷）
- [ ] Electron 打包验证（npm run dist）
- [ ] 后端 pytest 基础测试（API 端点）
- [ ] 统一版本号（前后端一致）
- [ ] 错误处理补充（部分路由缺少全局异常）
- [ ] 设置面板 SSE 状态提示（模型切换可见）

**风险**:
- SVG 渲染工程量不确定
- Electron 打包可能有路径/权限问题

### Phase 2 — V1.x 迭代

**目标**: 完善质量、提升中文检索、扩展模板

**任务**:
- [ ] 知识库嵌入模型换 BAAI/bge-m3
- [ ] 工程搜索中文分词（jieba + FTS5 自定义 tokenize）
- [ ] 前端 vitest 组件测试
- [ ] Playwright E2E 关键路径
- [ ] 多语言界面（中/英）
- [ ] HMI 变量导入导出
- [ ] 代码 Diff 视图
- [ ] 新 SCL 模板（电梯/停车场/HVAC 手写补全）

**风险**:
- 嵌入模型切换需要重建索引
- Playwright + Electron 的 E2E 配置复杂

### Phase 3 — V2.0

**目标**: AI Agent 直连 PLC 运行态

**任务**:
- [ ] TIA Openness 深度集成（AI 直接写块到 TIA Portal）
- [ ] OPC UA MCP 验证（运行时数据监控）
- [ ] plc-mcp-bridge 生产环境稳定
- [ ] AI Agent 编排（复杂任务自动拆解）
- [ ] RBAC 权限控制
- [ ] 安全链实机验证
- [ ] 3-5 真实 PLC 工程师试用反馈

**风险**:
- 工业安全责任（停机/设备损坏）
- 工厂内网环境复杂
- 需要真实的硬件测试环境

---

## 7. 环境配置

### Python 版本
- Python 3.13.2
- 路径: `D:\Python3\python.exe`

### Node 版本
- Node.js 18+（推荐 20+）
- npm 对应版本

### pip 依赖（父项目）
详见 `requirements.txt`：
- fastapi, uvicorn — Web 框架
- chromadb — 向量数据库
- openai, anthropic — LLM SDK
- pymupdf, python-docx — 文档解析
- python-snap7 — S7 协议
- pydantic-settings — 配置管理
- asyncua — OPC UA
- pymodbus — Modbus
- mcp — MCP SDK
- pytest, pytest-asyncio — 测试

### npm 依赖（前端）
详见 `frontend/package.json`：
- react, react-dom — UI 框架
- lucide-react — 图标
- react-markdown — Markdown 渲染
- electron, electron-builder — 桌面壳
- vite, tailwindcss — 构建

### 环境变量（.env）
详见 `.env.example`：
- `DEEPSEEK_API_KEY` — 必填
- `TIA_PROJECT_PATH` — TIA 项目路径
- `TIA_INSTALL_DIR` — TIA 安装目录
- `PLCSIM_ADV_DIR` — PLCSIM 目录
- `GOLDEN_*` — Golden backup 路径
- `FACTORY_IO_DIR` — Factory I/O 目录
- `S7_PLC_IP` — PLC IP（默认 192.168.0.110）

### 启动方式
```bash
# 开发模式（前后端分离）
cd ai-plc-assistant
start.bat                    # 一键启动
# 或分别启动：
start_backend.bat            # 后端 → 127.0.0.1:8005
start_frontend.bat           # 前端 → Vite + Electron

# 生产打包
cd ai-plc-assistant/frontend
npm run dist                 # electron-builder + NSIS
```

### 端口说明
- 后端: 8005
- 前端 Vite Dev: 5173
- PLCSIM: 192.168.0.110:102
- Factory I/O: 192.168.0.1

---

## 8. Prompt 与 AI 工作流

### System Prompt（内置）
```
你是一名资深的西门子PLC工程师，精通TIA Portal V21编程。
专业能力：
- SCL/LAD/FBD/STL 编程
- S7-1200/1500 系列
- IEC 61131-3 标准
- 匈牙利命名法（bStart、qMotor、rSpeed）
- 安全编程原则（互锁、急停、故障处理）
```

### Prompt 模板（22 个）
存储在 `backend/data/prompts.json`，覆盖：
- 交通灯/步进顺控/报警管理/模拟量处理
- 电机正反转/PID 调节/Modbus 通信
- 水泵站/冷却塔/包装机/SBR/CIP/立体仓库/AGV
- 电梯控制/停车场管理/HVAC/VAV/中央冷站
- 代码解释/IO 表生成

### RAG 工作流
```
用户问题
  → ChromaDB cosine 相似度检索（top_k=5）
  → 拼接为 "【参考文档】" 上下文
  → 注入 system prompt + RAG 上下文 → LLM
  → 返回带引用的回答
```

### LLM 自动切换
```
主模型失败（如 DeepSeek 超时）
  → 按 PROVIDER_ORDER 逐个尝试
  → deepseek → openai → kimi → claude → custom
  → 第一个成功的返回
  → 全部失败则抛异常
```

### MCP 配置
`.mcp.json` 配置 plc-mcp-kit：
```json
{
  "mcpServers": {
    "plc-mcp-kit": {
      "command": "D:\\Python3\\python.exe",
      "args": ["-m", "mcp_common.server"],
      "env": {
        "S7_PLC_IP": "192.168.0.110",
        "S7_RACK": "0",
        "S7_SLOT": "1"
      }
    }
  }
}
```

### 代码模板全链路
```
前端弹窗
  → GET /api/knowledge/code-templates（列表）
  → GET /api/knowledge/code-templates/{name}（内容）
  → 后端读 plc-code-templates/siemens-scl/ 目录
  → 返回 .scl 源码 + IO 表解析 / .md 文档
  → 前端 CodeTemplateModal 展示 + 复制按钮
```

### 梯形图模板全链路
```
前端弹窗
  → GET /api/knowledge/ladder-templates（列表元数据）
  → GET /api/knowledge/ladder-templates/{name}（完整 JSON + 文本化展示）
  → 后端读 mcp-servers/tia-mcp/templates/ 目录
  → 返回结构化 JSON + IO 表 + 网络文本化
```

---

## 9. 待办事项

### 高优先级

| # | 事项 | 原因 |
|---|------|------|
| 1 | 梯形图 SVG 可视化 | 核心功能缺陷，无图形化展示 |
| 2 | Electron 打包验证 | 配置已完成但未测试，无法分发 |
| 3 | 后端 pytest 基础测试 | 零覆盖率，不敢重构 |
| 4 | 统版本号（前后端） | `main.py=0.1.0` vs `package.json=1.0.0` |
| 5 | 知识库嵌入模型升级 | all-MiniLM-L6-v2 中文差，换 bge-m3 |

### 中优先级

| # | 事项 | 原因 |
|---|------|------|
| 1 | 工程搜索中文分词 | FTS5 LIKE 搜索性能低、准确率差 |
| 2 | Playwright E2E 测试 | 保障发布质量 |
| 3 | 补全 SCL 模板（电梯/停车场/HVAC） | Deep Research 断流未完成 |
| 4 | LLM 切换前端提示 | 用户看不见切换，体验差 |
| 5 | SSE 对话后端完善 | 当前 `/api/chat` 返回完整 JSON（非流式） |

### 低优先级

| # | 事项 | 原因 |
|---|------|------|
| 1 | 多语言界面 | 目前无海外用户需求 |
| 2 | 代码 Diff 视图 | 体验优化而非功能缺失 |
| 3 | RBAC 权限控制 | V2.0 多用户场景 |
| 4 | 工业机器人集成 | 未开始，无依赖 |
| 5 | 统一编排层 | Phase 5，依赖前面所有 |

---

## 10. 给下一任 AI 工程师的说明

欢迎接手这个项目！以下是你快速上手的关键路径：

### 首先阅读的文件（按顺序）

1. **`ARCHITECTURE.md`** — 系统架构总览（10 分钟）
2. **`DECISIONS.md`** — 技术决策记录，理解为什么这样设计（15 分钟）
3. **`PROJECT_STATUS.md`** — 当前状态和待办（5 分钟）
4. **`CLAUDE.md`** — 项目指令和约束（5 分钟）
5. **`backend/main.py`** — 后端入口，看路由注册和模块依赖（5 分钟）
6. **`backend/llm/service.py`** — LLM 调用层核心（10 分钟）
7. **`frontend/src/App.jsx`** — 前端编排层（5 分钟）
8. **`frontend/src/api.js`** — API 通信层（5 分钟）

### 当前最应该解决的问题

1. **SVG 梯形图可视化** — 这是用户最直观感受的功能缺陷
2. **基础测试覆盖** — 没有测试不敢改代码，形成恶性循环
3. **Electron 打包** — 配置有但未验证，实际交付需要

### 最容易踩坑的地方

1. **ChromaDB 路径** — 是 `data/vector_db` 不是 `data/chroma_db`，删错会丢数据
2. **端口 8005** — 后端跑在 8005 不是默认 8000，所有前端 API_BASE 和 proxy 都配了这个端口
3. **git push 需要代理** — 系统代理 127.0.0.1:7890，已移除 git http.proxy 配置
4. **Windows 编码** — bat 文件必须 GBK 编码，Python 源码 UTF-8
5. **Python 路径** — 用 `D:\Python3\python.exe`，不是系统默认
6. **TiaCommander 已过期**（2026-06-19）— 自研 TiaWorker 替代
7. **Factory I/O 走 PLCSIM TCP/IP** — 需要先 `switch_to_tcpip`
8. **Pydantic v2 语法** — 全项目用 Pydantic v2（`model_config` 不是 `Config` 类）

### 如何最快理解项目

1. 先读 `ARCHITECTURE.md` 的**系统总览图**，理解 4 层架构
2. 然后读 `DECISIONS.md` 的 **D-001 到 D-012**，理解 12 个关键决策
3. 然后读 `backend/main.py` 看**数据流**如何串联
4. 然后读 `frontend/src/App.jsx` 看 UI 如何编排
5. 最后逐个读 `backend/routes/` 下的路由文件

### 关键设计哲学

- **安全第一** — 所有写入操作经互锁 + 影子仿真 + 审计日志
- **本地优先** — 工厂内网无法访问云服务，所有数据库本地部署
- **AI 辅助人，不替代人** — 生成代码需工程师审核
- **中文用户体验** — 界面/Prompt/注释都用中文
- **匈牙利命名法** — PLC 代码用 bStart/qMotor/rSpeed 前缀

### 联系方式

项目由 @yihefeikong-rgb 维护，所有设计文档在 `docs/` 和 `ai-plc-assistant/` 下。

---

*交接文档到此结束。祝新工程师顺利接手！*
