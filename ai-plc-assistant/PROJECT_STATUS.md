# AI PLC Assistant 项目状态报告

更新时间：2026-06-17 | 更新人：Claude Code

---

## 一、项目目标

打造一个面向 PLC 工程师的本地 AI 开发助手，覆盖 **程序生成 → 知识检索 → 工程复用 → 故障诊断** 全流程，让工程师用自然语言完成 PLC 编程工作。

核心理念：**AI 辅助人，而不是替代人。** 所有代码生成结果需工程师审核确认，AI 定位是"加速器"而非"自动驾驶"。

---

## 二、当前版本

| 项 | 值 |
|---|---|
| 版本号 | V1.0（内部标记 V1.5） |
| 开发状态 | 功能基本完整，待收尾 + 自动化测试 |
| 后端行数 | ~2,800 行 Python（18 文件，32 API 路由） |
| 前端行数 | ~2,400 行 JSX（15 组件） |
| 数据库 | ChromaDB（向量）+ SQLite FTS5（全文）+ SQLite（业务） |

### 技术栈

```
Frontend:    Electron 31 + React 18 + Tailwind 3 + Vite 5 + Lucide React
Backend:     Python 3.13 + FastAPI 0.111 + Uvicorn
Database:    ChromaDB 0.5（向量检索）+ SQLite 3（FTS5 全文索引 + 业务持久化）
AI SDK:      OpenAI SDK（OpenAI 兼容）+ Anthropic SDK（Claude）
Document:    PyMuPDF（PDF）+ python-docx（DOCX）
```

### 启动方式

```
start.bat          # 一键启动前后端
├── backend:       python main.py → 127.0.0.1:8005
└── frontend:      npm run dev → Vite + Electron
```

---

## 三、已完成功能

### 3.1 AI 对话系统

- [x] **5 模型供应商**：DeepSeek / OpenAI / Kimi / Claude / 自定义
- [x] **流式输出**（前端支持，后端 SSE 待完善）
- [x] **模型自动切换**：主模型失败自动尝试下一个已配置模型
- [x] **PLC 系统 Prompt**：内置专业系统提示词（匈牙利命名、安全原则）
- [x] **RAG 增强**：聊天时自动检索知识库注入上下文
- [x] **对话持久化**：SQLite 存储，多会话切换

### 3.2 专用工作台（独立 Tab 页面）

- [x] **梯形图生成**：自然语言 → LLM → 结构化输出 → SCL/XML/CSV/HMI 导出
- [x] **代码解析**：粘贴 PLC 代码 → AI 分析（功能/变量/流程/安全/优化）
- [x] **IO 表生成**：设备描述 → AI 生成完整 IO 分配表（DI/DO/AI/AO）
- [x] **故障诊断**：故障描述 + 错误码 → AI 诊断（原因/排查步骤/预防）

### 3.3 知识库（ChromaDB 向量检索）

- [x] **文档导入**：PDF / DOCX / TXT
- [x] **自动分块**：段落级分割 + 句子级长文本切割 + 块间重叠
- [x] **向量搜索**：Cosine 相似度 + 分数阈值过滤
- [x] **文档管理**：列表 / 删除 / 统计

### 3.4 PLC 工程搜索（SQLite FTS5 全文索引）

- [x] **文件扫描**：递归扫描 XML / SCL / CSV / AWL
- [x] **结构化解析**：
  - XML：块头、变量成员、数据类型解析
  - SCL：FUNCTION_BLOCK/FUNCTION/DB/OB 识别 + 变量 + NETWORK 提取
  - CSV：IO 表解析
- [x] **全文搜索**：FTS5 英文查询 + LIKE 中文后备
- [x] **类型过滤**：按 plc_block / variable / network / io_entry 筛选
- [x] **工程导入**：.ap18 / .ap19 / .zip → 解压 → 索引 → 创建项目记录

### 3.5 代码导出

- [x] **SCL 源码**：TIA Portal 可直接粘贴的 FUNCTION_BLOCK/FC
- [x] **PLCopen XML**：标准交换格式
- [x] **CSV 标签表**
- [x] **HMI 标签 CSV**
- [x] **报警列表 CSV**
- [x] **JSON 变量导出**

### 3.6 Prompt 模板系统

- [x] **9 内置模板**：交通灯 / 电机正反转 / PID 调节 / Modbus / 步进顺控 / 模拟量处理 / 报警管理 / 代码解释 / IO 表生成
- [x] **变量系统**：模板参数 + 默认值 + 类型
- [x] **分类管理**：顺序控制 / 运动控制 / 过程控制 / 通信 / 信号处理 / 系统功能 / 辅助工具
- [x] **CRUD**：创建 / 读取 / 更新 / 删除

### 3.7 UI

- [x] **PLC IDE 风格**：VSCode Dark 配色（#1E1E1E / #252526 / #007ACC）
- [x] **四区域布局**：Toolbar + Sidebar + Workspace + Bottom Log Panel
- [x] **Tab 系统**：多页面切换，可关闭
- [x] **Dashboard 欢迎页**：快捷操作卡片 + 最近项目 + 最近对话 + 模板入口
- [x] **模型选择器**：工具栏下拉切换
- [x] **日志面板**：实时操作日志（Info / Warn / Error）
- [x] **侧栏**：工程 / 对话 / 知识库 / AI 工具 / 设置 分区折叠

### 3.8 设置

- [x] **5 供应商配置**：API Key / Base URL / 模型选择
- [x] **测试按钮**：点击验证连接 + 延迟显示
- [x] **PLC 默认值**：PLC 类型 / TIA 版本 / 语言
- [x] **API Key 遮盖**：前端显示时遮盖，更新时跳过未更改的遮盖值

### 3.9 项目管理

- [x] **CRUD**：创建 / 读取 / 更新 / 删除
- [x] **最近打开**：按 last_opened_at 排序
- [x] **工程导入**：上传 .ap18/.zip → 解压 → FTS5 索引 → 项目记录

---

## 四、正在进行 / 待收尾

### 4.1 流式输出（SSE）

**当前状态**：前端有流式加载动画，后端 `/api/chat` 返回完整 JSON（非 SSE）

**问题**：长回复需等 LLM 全部生成完毕才显示，体验不佳

**方案**：后端改 SSE → 前端 EventSource 逐 token 渲染

**预计**：V1.0 正式版前完成

### 4.2 梯形图 SVG 可视化

**当前状态**：结构化文本 + ASCII 符号，无图形

**方案**：根据 structured.networks 数据渲染 SVG 梯形图符号

**预计**：V1.0 正式版前完成

### 4.3 Electron 打包

**当前状态**：`npm run pack` / `npm run dist` 已配置（electron-builder + NSIS）

**问题**：未实际测试打包后的运行

**预计**：V1.0 正式版前完成

### 4.4 自动化测试（零覆盖率）

**当前状态**：**完全没有任何测试**

**后端**：pytest 未安装，无 test 目录
**前端**：vitest 未安装，无 test 文件
**E2E**：Playwright 未配置

**优先级**：高。详见记忆 `project-testing-todo.md`

---

## 五、计划开发

### P1 — V1.0 正式版前必须完成

| 功能 | 理由 |
|------|------|
| 流式 SSE 输出 | 核心体验缺陷 |
| 梯形图 SVG 可视化 | 核心功能缺陷 |
| Electron 打包测试 | 无法交付 |
| 后端 pytest 基础测试 | 无测试不敢重构 |
| 错误处理统一（后端） | 部分路由缺少全局异常捕获 |

### P2 — V1.x 迭代

| 功能 | 价值 |
|------|------|
| 前端 vitest 组件测试 | 保障 UI 稳定性 |
| Playwright E2E 关键路径 | 保障发布质量 |
| 工程搜索中文分词优化 | 当前 LIKE 搜索准确率低 |
| 知识库多轮对话记忆 | 支持追问式 RAG |
| 代码对比（Diff）视图 | 查看 AI 修改前后差异 |
| HMI 变量导入/导出 | 完整工程流转闭环 |
| 多语言界面（中/英） | 海外用户支持 |

### P3 — V2.0

| 功能 | 价值 | 依赖 |
|------|------|------|
| TIA Openness 集成 | 直接从 AI 写块到 TIA Portal | TiaWorker 稳定 |
| OPC UA MCP 集成 | 运行时数据监控 | OPC UA MCP 验证 |
| AI 直连 PLC（S7） | AI Agent 直接操作运行态 | plc-mcp-bridge 稳定 |
| 多 Agent 编排 | 复杂任务自动拆解分配 | Phase 5 |
| RBAC 权限控制 | 多用户安全 | — |

---

## 六、项目目录结构

```
ai-plc-assistant/
├── start.bat                        # 一键启动脚本
├── start_backend.bat                # 仅启动后端
├── start_frontend.bat               # 仅启动前端
├── README.md
├── PROJECT_STATUS.md                # ← 本文件
│
├── backend/
│   ├── main.py                      # FastAPI 入口 + 路由注册
│   ├── config.py                    # Pydantic Settings + .env 加载
│   ├── requirements.txt             # Python 依赖
│   ├── .env                         # 环境变量（API Key 等）
│   │
│   ├── routes/
│   │   ├── chat.py                  # 1 路由：AI 对话 + RAG
│   │   ├── models.py                # 2 路由：模型列表
│   │   ├── knowledge.py             # 5 路由：知识库 CRUD
│   │   ├── search.py                # 5 路由：工程搜索
│   │   ├── generate.py              # 6 路由：梯形图生成 + 导出
│   │   ├── prompts.py               # 7 路由：Prompt 模板 CRUD
│   │   ├── conversations.py         # 7 路由：对话历史
│   │   ├── projects.py              # 7 路由：项目管理 + 导入
│   │   └── settings.py              # 4 路由：设置读写 + 测试
│   │
│   ├── llm/
│   │   └── service.py               # 5 模型路由 + 自动切换 + PLC Prompt
│   │
│   ├── knowledge/
│   │   ├── engine.py                # ChromaDB 引擎
│   │   ├── parsers.py               # PDF/DOCX/TXT 解析
│   │   └── chunker.py               # 文本分块器
│   │
│   ├── search/
│   │   ├── indexer.py               # SQLite FTS5 索引引擎
│   │   ├── scanner.py               # PLC 文件递归扫描
│   │   └── parsers.py               # XML/SCL/CSV/AWL 结构化解析
│   │
│   ├── generator/
│   │   ├── __init__.py              # LadderProgram 数据模型 + 解析器 + Demo
│   │   ├── workflow.py              # 生成工作流（LLM → demo 回退）
│   │   ├── scl_generator.py         # SCL 源码生成
│   │   ├── xml_generator.py         # PLCopen XML 生成
│   │   └── export_generator.py      # CSV/HMI/Alarm/JSON 导出
│   │
│   ├── storage/
│   │   ├── conversations.py         # 对话 SQLite 存储
│   │   ├── projects.py              # 项目 SQLite 存储
│   │   └── app_settings.py          # 设置 JSON 文件存储
│   │
│   └── data/
│       ├── conversations.db         # 对话数据
│       ├── projects.db              # 项目数据
│       ├── search_index.db          # FTS5 全文索引
│       ├── settings.json            # 应用设置
│       └── vector_db/               # ChromaDB 向量数据库
│
└── frontend/
    ├── package.json                 # Electron + React + 构建配置
    ├── vite.config.js               # Vite 配置
    ├── tailwind.config.js           # Tailwind 配置
    ├── postcss.config.js
    │
    ├── electron/
    │   ├── main.js                  # Electron 主进程
    │   └── preload.js               # Preload 脚本
    │
    └── src/
        ├── main.jsx                 # React 入口
        ├── App.jsx                  # 主应用（Tab 系统 + 布局 + 状态）
        ├── api.js                   # API 通信层
        ├── index.css                # 全局样式
        │
        └── components/
            ├── Dashboard.jsx        # 欢迎页
            ├── Sidebar.jsx          # 左侧导航
            ├── Toolbar.jsx          # 顶部工具栏
            ├── ChatArea.jsx         # AI 聊天
            ├── ContextPanel.jsx     # 右侧上下文面板
            ├── LogPanel.jsx         # 底部日志
            ├── CodeExplainer.jsx    # 代码解析工作台
            ├── FaultDiagnosis.jsx   # 故障诊断工作台
            ├── IoTableGenerator.jsx # IO 表生成工作台
            ├── SettingsPanel.jsx    # 设置页
            └── PromptTemplateModal.jsx # 模板选择弹窗
```

---

## 七、遇到的问题

### 问题 1：RAG 检索准确率有限

**现象**：中文文档的向量检索结果不如英文理想

**原因**：
- ChromaDB 默认使用的 all-MiniLM-L6-v2 对中文支持一般
- chunk_size=500 可能导致跨语义边界
- 无中文分词，按字符切割

**尝试方案**：
- 改用 Sentence Transformers 中文模型（如 paraphrase-multilingual-MiniLM-L12-v2）
- 增加段落级结构化分块（保留标题层级）

### 问题 2：工程搜索中文支持差

**现象**：FTS5 unicode61 对 CJK 不分词，中文搜索走 LIKE 后备，性能和准确率低

**尝试方案**：
- 引入 jieba 分词器自定义 FTS5 tokenize
- 或在应用层对中文 Query 做分词后拼接为 OR 查询

### 问题 3：生成器梯形图→SCL 转换很弱

**现象**：`_ladder_to_scl()` 函数只能处理最简单的串联触点和线圈，复杂逻辑需用户手动补写

**方案**：SCL 代码应直接由 LLM 生成，而非后处理梯形图 ASCII

### 问题 4：LLM 回退链路脆弱

**现象**：当 DeepSeek 不可用时自动切换到其他模型，但切换信息在前端只有一个 warn log，用户可能看不到

**方案**：在聊天界面显示模型切换提示

### 问题 5：前端全量放在一个 App.jsx

**现象**：所有状态管理、Tab 逻辑、对话管理集中在一个 306 行的 App.jsx 组件中

**问题**：继续迭代会变得难以维护

**方案**：提取自定义 hooks（useConversation、useProjects、useTabs）+ 拆分 Context

### 问题 6：无版本管理

**现象**：前端 package.json 版本固定 1.0.0，后端 main.py 版本 0.1.0，前后不一致

**方案**：统一为 V1.0.0，从配置文件读取

### 问题 7：`.env` 中存在明文 API Key

**现象**：DeepSeek API Key 直接写在 `.env` 中

**风险**：如果提交到 Git 会被泄露

**方案**：
- `.env` 已加入 `.gitignore`（需确认）
- 建议添加 `.env.example` 作为模板

---

## 八、希望获得的建议

1. **架构评审**：当前的模块划分（routes / llm / knowledge / search / generator / storage）是否合理？后续增长有没有隐患？

2. **RAG 优化路线**：中文工业文档（PDF 手册、SCL 源码）的检索应该怎么做才靠谱？

3. **Agent 设计**：目前 AI 只是被动回答。如果要做成主动 Agent（例如"监控这个变量，超限了提醒我"），应该怎么做？

4. **AI + PLC 的产品定位**：市面上没有直接的竞品。应该聚焦"代码生成"还是"运行态监控"，还是两者都要？

5. **商业化可行性**：这种本地部署的 AI 工具，在工业场景下怎么收费才合理？

6. **自动化测试策略**：对一个 Electron + FastAPI + ChromaDB 的项目，测试金字塔怎么搭才划算？

7. **接下来做什么**：V1.0 正式版应该优先修哪些问题？哪些功能可以砍？

---

## 九、快速参考

### API 路由总览（32 路由）

```
  POST /api/chat                    # AI 对话 + RAG
  GET  /api/models                  # 模型列表
  GET  /api/models/{id}             # 模型详情
  POST /api/knowledge/import        # 导入文档
  GET  /api/knowledge/search        # 搜索知识库
  GET  /api/knowledge/documents     # 文档列表
  DELETE /api/knowledge/documents/{id}
  GET  /api/knowledge/status        # 知识库统计
  GET  /api/search                  # 工程搜索
  POST /api/search/index            # 索引项目
  GET  /api/search/types            # 类型列表
  GET  /api/search/stats            # 搜索统计
  DELETE /api/search/index          # 清空索引
  POST /api/generate/ladder         # 梯形图生成
  POST /api/generate/ladder/scl     # SCL 生成
  POST /api/generate/ladder/xml     # XML 生成
  POST /api/generate/export         # 代码导出
  POST /api/generate/export/download
  POST /api/generate/prompt         # 调试 Prompt
  GET  /api/prompts                 # 模板列表
  GET  /api/prompts/categories       # 模板分类
  GET  /api/prompts/{id}            # 模板详情
  POST /api/prompts                 # 创建模板
  PUT  /api/prompts/{id}            # 更新模板
  DELETE /api/prompts/{id}          # 删除模板
  GET  /api/conversations           # 对话列表
  POST /api/conversations           # 创建对话
  GET  /api/conversations/{id}      # 对话详情
  PUT  /api/conversations/{id}      # 更新对话
  DELETE /api/conversations/{id}    # 删除对话
  POST /api/conversations/{id}/messages
  GET  /api/conversations/stats/overview
  GET  /api/projects                # 项目列表
  POST /api/projects                # 创建项目
  GET  /api/projects/{id}           # 项目详情
  PUT  /api/projects/{id}           # 更新项目
  DELETE /api/projects/{id}         # 删除项目
  POST /api/projects/import         # 导入工程
  GET  /api/settings                # 获取设置
  PUT  /api/settings                # 更新设置
  GET  /api/settings/providers      # 供应商列表
  POST /api/settings/test/{provider} # 测试连接
  GET  /api/health                  # 健康检查
```

### 关键依赖

| 包 | 用途 | 版本 |
|---|---|---|
| fastapi | API 框架 | 0.111 |
| chromadb | 向量检索 | 0.5.5 |
| openai | LLM SDK | 1.35 |
| anthropic | Claude SDK | 0.32 |
| PyMuPDF | PDF 解析 | 1.24 |
| python-docx | DOCX 解析 | 1.1 |
| electron | 桌面壳 | 31 |
| tailwindcss | UI 框架 | 3.4 |
| lucide-react | 图标 | 1.20 |
| react-markdown | Markdown 渲染 | 9.0 |
