# AI PLC Assistant — 系统架构

更新时间：2026-06-17

---

## 一、系统总览

```
┌─────────────────────────────────────────────────────────┐
│                    Electron 桌面壳                        │
│  ┌───────────────────────────────────────────────────┐  │
│  │              React + Tailwind 前端                  │  │
│  │                                                     │  │
│  │  App.jsx (编排层, 115行)                             │  │
│  │    ├── useLogs        日志状态                       │  │
│  │    ├── useTabs        Tab 管理                      │  │
│  │    ├── useModels      模型选择                       │  │
│  │    ├── useProjects    项目 CRUD                     │  │
│  │    └── useConversation 对话 + 发送 + SSE             │  │
│  │                                                     │  │
│  │  api.js → HTTP/SSE → 127.0.0.1:8005                │  │
│  └──────────────────────┬────────────────────────────┘  │
└─────────────────────────┼───────────────────────────────┘
                          │ HTTP + SSE
                          ▼
┌─────────────────────────────────────────────────────────┐
│                 FastAPI 后端 (端口 8005)                  │
│                                                          │
│  main.py                                                 │
│    ├── 全局异常处理 (422 / 500)                           │
│    ├── CORS 中间件                                       │
│    ├── 日志系统 (RotatingFileHandler)                     │
│    └── Lifespan → 初始化所有引擎                          │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  routes/     │  │  llm/        │  │  storage/      │  │
│  │  9 路由模块   │  │  service.py  │  │  SQLite 持久化  │  │
│  │  33 端点     │  │  5 模型路由   │  │  conversations │  │
│  │             │  │  自动切换     │  │  projects      │  │
│  │             │  │  SSE 流式     │  │  settings.json │  │
│  └──────┬──────┘  └──────┬───────┘  └───────┬────────┘  │
│         │                │                   │           │
│  ┌──────┴──────┐  ┌──────┴───────┐  ┌───────┴────────┐  │
│  │ knowledge/  │  │  generator/  │  │  search/        │  │
│  │ ChromaDB    │  │  SCL/XML/CSV │  │  SQLite FTS5    │  │
│  │ 向量检索    │  │  LLM→结构化  │  │  全文索引       │  │
│  └─────────────┘  └──────────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
    ┌──────────┐     ┌────────────┐     ┌────────────┐
    │ ChromaDB │     │ DeepSeek   │     │ SQLite     │
    │ 向量数据库│     │ OpenAI     │     │ FTS5 索引  │
    │ (本地磁盘)│     │ Kimi       │     │ 对话/项目  │
    └──────────┘     │ Claude     │     └────────────┘
                     │ 自定义     │
                     └────────────┘
```

---

## 二、数据流

### 2.1 AI 对话（SSE 流式）

```
用户输入文本
    │
    ▼
useConversation.handleSend()
    │
    ├── 梯形图关键词? ──Yes──→ POST /api/generate/ladder (非流式)
    │                              │
    │                              ▼
    │                         LLM → parse_raw_output → LadderProgram
    │                              │
    │                              ▼
    │                         结构化渲染 (变量表 + Network)
    │
    └── No ──→ streamChat() → POST /api/chat/stream (SSE)
                    │
                    ▼
              后端 RAG 检索 (ChromaDB cosine similarity)
                    │
                    ▼
              注入 system prompt + RAG 上下文
                    │
                    ▼
              LLM chat_stream() → 逐 token yield
                    │
                    ▼
              SSE: data: {"token": "..."} × N
              SSE: data: {"done": true, "model": "deepseek"}
              SSE: data: [DONE]
                    │
                    ▼
              前端逐 token 拼接 → ReactMarkdown 实时渲染
                    │
                    ▼
              对话持久化 → SQLite conversations.db
```

### 2.2 知识库导入

```
用户上传 PDF/DOCX/TXT
    │
    ▼
POST /api/knowledge/import
    │
    ▼
临时文件保存 → parsers.py 解析为纯文本
    │
    ▼
chunker.py 分块 (500字/块, 100字重叠)
    │
    ▼
ChromaDB.add() → all-MiniLM-L6-v2 自动嵌入
    │
    ▼
返回 document_id + chunk_count
```

### 2.3 工程搜索

```
用户输入搜索词
    │
    ▼
GET /api/search?q=...
    │
    ├── 英文 → FTS5 MATCH 查询 (高效)
    │
    └── 中文 → LIKE 后备查询 (准确率低)
    │
    ▼
返回匹配条目 (块名/变量名/网络/IO)
```

### 2.4 代码导出

```
LadderProgram (结构化数据)
    │
    ├── scl_generator.py   → FUNCTION_BLOCK ... END_FUNCTION_BLOCK
    ├── xml_generator.py   → PLCopen XML (可导入 TIA Portal)
    ├── export_generator.py → CSV 标签表 / HMI 变量 / 报警列表 / JSON
    │
    ▼
前端下载
```

---

## 三、模块依赖

```
main.py
  ├── routes/chat.py ──────→ llm/service.py ──→ OpenAI SDK / Anthropic SDK
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
  │                           ├── search/scanner.py (递归扫描)
  │                           └── search/parsers.py (XML/SCL/CSV/AWL)
  ├── routes/projects.py ──→ storage/projects.py (SQLite)
  ├── routes/conversations.py → storage/conversations.py (SQLite)
  ├── routes/prompts.py ───→ data/prompts.json (文件持久化)
  ├── routes/models.py ────→ storage/app_settings.py
  └── routes/settings.py ──→ storage/app_settings.py (JSON)
```

**外部依赖方向：全部向外调用，无外部回调**
- LLM API: 出站 HTTPS（DeepSeek/OpenAI/Kimi/Claude）
- 数据库: 本地文件（ChromaDB 目录 + SQLite 文件）
- 无消息队列、无 Redis、无外部数据库

---

## 四、API 结构（33 端点）

| 域 | 前缀 | 端点数 | 说明 |
|---|---|---|---|
| 对话 | `/api/chat` | 2 | 非流式 + SSE 流式 |
| 模型 | `/api/models` | 2 | 列表 + 详情 |
| 知识库 | `/api/knowledge` | 5 | 导入 / 搜索 / 列表 / 删除 / 统计 |
| 搜索 | `/api/search` | 5 | 全文搜索 / 索引 / 类型 / 统计 / 清空 |
| 生成 | `/api/generate` | 6 | 梯形图 / SCL / XML / 导出 / 下载 / Prompt |
| 模板 | `/api/prompts` | 7 | CRUD + 分类 |
| 对话历史 | `/api/conversations` | 7 | CRUD + 消息 + 统计 |
| 项目 | `/api/projects` | 7 | CRUD + 导入 |
| 设置 | `/api/settings` | 4 | 读写 + 供应商列表 + 测试 |
| 系统 | `/api/health` | 1 | 健康检查 |

---

## 五、数据库结构

### 5.1 conversations.db (SQLite)

```sql
conversations (
    id          TEXT PRIMARY KEY,     -- UUID
    title       TEXT,
    model_id    TEXT,                 -- 使用的模型
    created_at  REAL,
    updated_at  REAL
)

messages (
    id              TEXT PRIMARY KEY, -- UUID
    conversation_id TEXT FK,
    role            TEXT,             -- user / assistant / system
    content         TEXT,
    msg_type        TEXT,             -- text / ladder
    metadata        TEXT,             -- JSON
    created_at      REAL
)
```

### 5.2 projects.db (SQLite)

```sql
projects (
    id              TEXT PRIMARY KEY,
    name            TEXT,
    path            TEXT,             -- 工程文件路径
    plc_type        TEXT,             -- S7-1200 / S7-1500
    tia_version     TEXT,             -- V18 / V19
    language        TEXT,             -- SCL / LAD
    description     TEXT,
    created_at      REAL,
    updated_at      REAL,
    last_opened_at  REAL
)
```

### 5.3 search_index.db (SQLite + FTS5)

```sql
entries (
    id          INTEGER PRIMARY KEY,
    file_path   TEXT,
    type        TEXT,       -- plc_block / variable / network / io_entry / generic
    name        TEXT,
    block_name  TEXT,
    block_type  TEXT,       -- FB / FC / DB / OB
    content     TEXT,
    line        INTEGER,
    indexed_at  REAL
)

entries_fts USING fts5 (    -- 全文索引 (虚拟表)
    name, block_name, content,
    content='entries', content_rowid='id'
)
```

### 5.4 ChromaDB (向量数据库)

```
Collection: plc_knowledge
  ├── Embedding: all-MiniLM-L6-v2 (384 维)
  ├── Distance: cosine
  └── Metadata per chunk:
        document_id   TEXT
        filename      TEXT
        extension     TEXT
        chunk_index   INT
        total_chunks  INT
```

### 5.5 settings.json (文件)

```json
{
    "deepseek_api_key": "sk-...",
    "deepseek_base_url": "https://api.deepseek.com",
    "deepseek_model": "deepseek-v4-flash",
    "openai_api_key": "",
    "kimi_api_key": "",
    "claude_api_key": "",
    "custom_api_key": "",
    "default_plc_type": "S7-1200",
    "default_tia_version": "V18",
    "default_language": "SCL"
}
```

---

## 六、前端组件树

```
<ErrorBoundary>
  <App>                                    -- 编排层 (115行)
    ├── <Toolbar>                          -- 模型选择 + 菜单
    ├── Tab Bar                            -- 内联 Tab 切换
    ├── <Sidebar>                          -- 工程/对话/知识库/工具/设置
    ├── Workspace (按 activeTab 切换)
    │   ├── <Dashboard>                    -- 欢迎页
    │   ├── <ChatArea>                     -- AI 聊天 (SSE)
    │   ├── <CodeExplainer>                -- 代码解析 (SSE)
    │   ├── <FaultDiagnosis>               -- 故障诊断 (SSE)
    │   ├── <IoTableGenerator>             -- IO 表生成 (SSE)
    │   └── <SettingsPanel>                -- 设置
    ├── <ContextPanel>                     -- 右侧上下文
    ├── <LogPanel>                         -- 底部日志
    └── <PromptTemplateModal>              -- 模板弹窗
  </App>
</ErrorBoundary>
```
