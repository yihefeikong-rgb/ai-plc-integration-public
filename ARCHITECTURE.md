# 系统架构文档 — AI 接入 PLC

> 生成时间：2026-06-18
> 供下一任 AI 工程师快速理解系统全貌

---

## 一、系统总览（4 层架构）

```
┌────────────────────────────────────────────────────────────┐
│  Layer 1: 桌面应用层 (AI PLC Assistant)                    │
│  ┌──────────────────┐  ┌────────────────────────────────┐  │
│  │  Electron + React │  │  FastAPI 后端 (8005)          │  │
│  │  前端 (JSX)       │  │  Python 3.13                  │  │
│  │  11 组件 + 5 hooks│◄─┤  33 API 端点                  │  │
│  └──────────────────┘  │  5 模块 (llm/knowledge/search/ │  │
│                        │    generator/storage)           │  │
│                        └────────┬───────────────────────┘  │
└─────────────────────────────────┼──────────────────────────┘
                                  │
┌─────────────────────────────────┼──────────────────────────┐
│  Layer 2: MCP 协议层           │                           │
│  ┌─────────────────────────────▼────────────────────────┐  │
│  │  plc-mcp-bridge (65 tools, S7 + TIA + PLCSIM + FIO) │  │
│  │  tia-mcp/TiaWorker (C# TIA Openness)                 │  │
│  │  opcua-mcp / modbus-mcp / mitsubishi-mcp (骨架)      │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────┼──────────────────────────┐
│  Layer 3: 工程 + 仿真层        │                           │
│  ┌──────────┐  ┌──────────┐  ┌─────────────┐              │
│  │TIA Portal│  │ PLCSIM   │  │Factory I/O  │              │
│  │V18/V21   │  │Advanced  │  │3D 仿真场景  │              │
│  │Openness  │  │V8.0      │  │             │              │
│  └──────────┘  └──────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────┼──────────────────────────┐
│  Layer 4: 安全层 (贯穿所有层)                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │互锁规则  │  │影子仿真  │  │审计日志  │  │写入熔断  │  │
│  │YAML 配置 │  │仿真验证  │  │链式哈希  │  │异常保护  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、AI PLC Assistant 内部架构

### 2.1 前端组件树

```
<ErrorBoundary>
  <App>                          ← 编排层，5 个 custom hooks
    ├── <Toolbar>                ← 模型选择 + 操作按钮
    ├── Tab Bar                  ← 内联 Tab 切换
    ├── <Sidebar>                ← 侧栏（工程/对话/知识库/工具/设置）
    ├── Workspace (按 activeTab 切换)
    │   ├── <Dashboard>          ← 欢迎页
    │   ├── <ChatArea>           ← AI 聊天（SSE 流式）
    │   ├── <CodeExplainer>      ← 代码解析（SSE）
    │   ├── <FaultDiagnosis>     ← 故障诊断（SSE）
    │   ├── <IoTableGenerator>   ← IO 表生成（SSE）
    │   └── <SettingsPanel>      ← 设置
    ├── <ContextPanel>           ← 右侧上下文
    ├── <LogPanel>               ← 底部日志
    ├── <PromptTemplateModal>    ← Prompt 模板弹窗
    ├── <CodeTemplateModal>      ← SCL 代码模板弹窗
    └── <LadderTemplateModal>    ← 梯形图模板弹窗
  </App>
</ErrorBoundary>
```

### 2.2 核心数据流

```
── SSE 对话 ──────────────────────────────────────────
用户输入 → streamChat() → POST SSE → RAG → LLM → 逐 token → 渲染

── 知识库导入 ──────────────────────────────────────
上传文档 → parsers.py → chunker.py → ChromaDB

── 梯形图生成 ──────────────────────────────────────
自然语言 → LLM LadderProgram → workflow → SCL/XML/CSV 导出

── 工程搜索 ─────────────────────────────────────────
选择目录 → scanner.py → parsers.py → FTS5 索引 → 搜索

── 代码模板 ─────────────────────────────────────────
GET list → GET {name} → 读文件系统 → 前端展示
```

### 2.3 后端模块依赖图

```
main.py
  ├── routes/chat.py ──────→ llm/service.py ──→ OpenAI / Anthropic SDK
  │     └── RAG ──────────→ knowledge/engine.py ──→ ChromaDB
  ├── routes/generate.py ──→ generator/workflow.py ──→ llm/service.py
  │                           ├── generator/__init__.py (LadderProgram)
  │                           ├── generator/scl_generator.py
  │                           ├── generator/xml_generator.py
  │                           └── generator/export_generator.py
  ├── routes/knowledge.py ─→ knowledge/engine.py
  │                           ├── knowledge/parsers.py (PDF/DOCX/TXT)
  │                           └── knowledge/chunker.py
  ├── routes/search.py ────→ search/indexer.py (SQLite FTS5)
  │                           ├── search/scanner.py
  │                           └── search/parsers.py (XML/SCL/CSV/AWL)
  ├── routes/projects.py ──→ storage/projects.py (SQLite)
  ├── routes/conversations.py → storage/conversations.py (SQLite)
  ├── routes/prompts.py ───→ data/prompts.json
  ├── routes/models.py ────→ storage/app_settings.py
  └── routes/settings.py ──→ storage/app_settings.py
```

### 2.4 API 端点一览（33 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/chat | AI 对话（非流式，当前未用） |
| POST | /api/chat/stream | AI 对话（SSE 流式） |
| GET | /api/models | 模型列表 |
| GET | /api/models/{id} | 模型详情 |
| POST | /api/knowledge/import | 导入文档到知识库 |
| GET | /api/knowledge/search | 搜索知识库 |
| GET | /api/knowledge/documents | 文档列表 |
| DELETE | /api/knowledge/documents/{id} | 删除文档 |
| GET | /api/knowledge/status | 知识库统计 |
| GET | /api/knowledge/code-templates | SCL 代码模板列表 |
| GET | /api/knowledge/code-templates/{name} | SCL 代码模板内容 |
| GET | /api/knowledge/ladder-templates | 梯形图模板列表 |
| GET | /api/knowledge/ladder-templates/{name} | 梯形图模板详情 |
| GET | /api/search | 工程搜索 |
| POST | /api/search/index | 索引项目 |
| GET | /api/search/types | 类型列表 |
| GET | /api/search/stats | 搜索统计 |
| DELETE | /api/search/index | 清空索引 |
| POST | /api/generate/ladder | 梯形图生成 |
| POST | /api/generate/ladder/scl | SCL 生成 |
| POST | /api/generate/ladder/xml | XML 生成 |
| POST | /api/generate/export | 代码导出 |
| POST | /api/generate/export/download | 导出下载 |
| POST | /api/generate/prompt | 调试 Prompt |
| GET | /api/prompts | 模板列表 |
| GET | /api/prompts/categories | 分类列表 |
| GET | /api/prompts/{id} | 模板详情 |
| POST | /api/prompts | 创建模板 |
| PUT | /api/prompts/{id} | 更新模板 |
| DELETE | /api/prompts/{id} | 删除模板 |
| GET | /api/conversations | 对话列表 |
| POST | /api/conversations | 创建对话 |
| GET | /api/conversations/{id} | 对话详情 |
| PUT | /api/conversations/{id} | 更新对话 |
| DELETE | /api/conversations/{id} | 删除对话 |
| POST | /api/conversations/{id}/messages | 添加消息 |
| GET | /api/conversations/stats/overview | 统计 |
| GET | /api/projects | 项目列表 |
| POST | /api/projects | 创建项目 |
| GET | /api/projects/{id} | 项目详情 |
| PUT | /api/projects/{id} | 更新项目 |
| DELETE | /api/projects/{id} | 删除项目 |
| POST | /api/projects/import | 导入工程 |
| GET | /api/settings | 获取设置 |
| PUT | /api/settings | 更新设置 |
| GET | /api/settings/providers | 供应商列表 |
| POST | /api/settings/test/{provider} | 测试连接 |
| GET | /api/health | 健康检查 |

---

## 三、plc-mcp-bridge 架构

### 工具分类（65 个）

| 模块 | 工具数 | 说明 |
|------|--------|------|
| S7 运行态 | 4 | connect/disconnect/read/write |
| TIA 工程 | 22 | 创建/删除/编译/下载块/DB/UDT |
| 标签表 | 5 | CRUD + 冲突检测 + CSV 导出 |
| 监控表 | 2 | CRUD |
| PLCSIM | 6 | 创建/启动/停止/切换/状态 |
| Factory I/O | 3 | 配置/启动/联动 |
| Pipeline | 1 | 一键全流程 |
| 其他 | 22 | 导出/备份/诊断/搜索 |

### 数据流

```
Claude Code / AI Agent
  │ MCP 协议
  ▼
plc-mcp-bridge/server.py
  ├── s7_adapter.py          ← S7 读写（python-snap7）
  ├── tools_s7.py            ← S7 工具定义
  ├── tools_blocks.py        ← 块操作
  ├── tools_tags.py          ← 标签表
  ├── tools_project.py       ← 项目管理
  ├── tools_plcsim.py        ← PLCSIM 管理
  ├── tools_hardware.py      ← 硬件配置
  ├── tools_export.py        ← 导出
  ├── tools_diagnostics.py   ← 诊断
  ├── tools_types.py         ← UDT 管理
  ├── tools_pipeline.py      ← P3 流水线
  └── _helpers.py            ← 工具函数
```

---

## 四、TIA Worker 架构

```
tia-mcp/
├── server.py                 ← MCP 服务器入口
├── TiaWorker/Program.cs      ← C# TIA Openness 核心
│   ├── SCL 代码写入
│   ├── LAD 梯形图生成
│   ├── 块创建/删除/编译
│   ├── PLCSIM 下载
│   └── Golden backup/restore
├── CartGen/Program.cs        ← 料车 3 循环生成器
├── templates/                ← 20 个 JSON 梯形图模板
├── config.yaml               ← TIA 配置
├── config_loader.py          ← 配置加载
├── download_to_plcsim.py     ← 下载流程（5 级降级）
├── dl_plcsim_gui.py          ← GUI 模式下载
├── plcsim_advanced.py        ← PLCSIM 操作
├── ladder_renderer.py        ← 梯形图渲染
├── lad_creator.py            ← LAD 创建
├── generate_scl.py           ← SCL 生成
├── fio_mapper.py             ← Factory I/O 映射
└── ...
```

### 下载降级策略

```
1. TiaWorker (C# 直接下载)       ← 最佳
2. TiaWorker GUI 模式
3. python 脚本 (plcsim API)
4. UI 手动操作 (用户指导)
5. Golden restore (绕过 TIA)    ← 最稳
```

---

## 五、安全层架构

### 互锁验证

```yaml
# safety/interlock-rules.yml
rules:
  - name: "急停=0 禁止启动"
    conditions:
      - bEStop == false
    blocked_actions:
      - write_output
      - start_motor
```

### 写入校验链

```
用户请求写入
  → safety/validator.py: 互锁规则检查
  → safety/shadow_simulator.py: 仿真验证
  → safety/audit.py: 审计日志（链式哈希）
  → 实际写入 PLC
  → 熔断机制：连续异常自动停止
```

---

## 六、数据库结构

### conversations.db (SQLite)
```sql
conversations (id TEXT PK, title TEXT, model_id TEXT, created_at REAL, updated_at REAL)
messages (id TEXT PK, conversation_id TEXT FK, role TEXT, content TEXT, msg_type TEXT, metadata TEXT, created_at REAL)
```

### projects.db (SQLite)
```sql
projects (id TEXT PK, name TEXT, path TEXT, plc_type TEXT, tia_version TEXT, language TEXT, description TEXT, created_at REAL, updated_at REAL, last_opened_at REAL)
```

### search_index.db (SQLite + FTS5)
```sql
entries (id INTEGER PK, file_path TEXT, type TEXT, name TEXT, block_name TEXT, block_type TEXT, content TEXT, line INTEGER, indexed_at REAL)
entries_fts USING fts5 (name, block_name, content, content='entries', content_rowid='id')
```

### ChromaDB
```
Collection: plc_knowledge
  Embedding: all-MiniLM-L6-v2 (384 维)  ← 计划换 BAAI/bge-m3
  Distance: cosine
  Metadata: document_id, filename, extension, chunk_index, total_chunks
```

### settings.json
```json
{
  "deepseek_api_key": "sk-...",
  "deepseek_model": "deepseek-v4-flash",
  "default_plc_type": "S7-1200",
  "default_tia_version": "V18",
  ...
}
```

---

## 七、代码模板体系

### SCL 模板（22 个）
路径: `plc-code-templates/siemens-scl/`
格式: `.scl`（源码）+ `.md`（文档说明）
来源: Deep Research 搜索 + 手工编写 + SCL 转换

### LAD 梯形图模板（20 个）
路径: `mcp-servers/tia-mcp/templates/`
格式: JSON（结构化网络）
来源: 从星三角/报警灯/传送带等经典案例手工编写 JSON

### Prompt 模板（22 个）
路径: `backend/data/prompts.json`
格式: JSON（含变量系统 + 分类）

### PLCopen XML（2 个）
路径: `plc-code-templates/`
格式: 标准 PLCopen XML

---

## 八、部署架构

### 开发环境
```
Windows 11
├── TIA Portal V18 (工程站)
├── PLCSIM Advanced V8.0 (仿真)
├── Factory I/O (3D 场景)
├── Python 3.13 (后端)
├── Node.js 18+ (前端)
└── Git (版本控制)
```

### 一键启动
```bash
ai-plc-assistant/start.bat
  ├── backend:  python main.py → 127.0.0.1:8005
  ├── frontend: npm run dev → Vite 5173 + Electron
  └── 自动等待后端就绪后启动前端
```

### 生产打包
```
npm run dist
  → vite build (React → dist/)
  → electron-builder (NSIS 安装包 → release/)
  → 单机运行，无需服务器
```
