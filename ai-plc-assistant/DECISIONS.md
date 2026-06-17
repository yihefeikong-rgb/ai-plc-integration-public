# AI PLC Assistant — 技术决策记录

更新时间：2026-06-17

每条记录回答三个问题：**选了什么、为什么选它、为什么不选别的。**

---

## D-001: 后端框架 → FastAPI

**选择**: FastAPI + Uvicorn

**原因**:
- 原生 async 支持，SSE 流式输出自然
- 自带 OpenAPI 文档（/docs），前后端联调效率高
- Pydantic 数据验证内置，减少样板代码
- Python 生态与 AI/ML 库（OpenAI SDK、ChromaDB、snap7）无缝衔接

**为什么不选**:
- Django: 太重，ORM/Admin/模板引擎全用不上
- Flask: 没有原生 async，SSE 实现更复杂
- Node.js: Python snap7 绑定不可替代，换语言意味着重写 PLC 通信层

---

## D-002: 前端框架 → Electron + React

**选择**: Electron 31 + React 18 + Vite 5 + Tailwind 3

**原因**:
- 目标用户是工厂 PLC 工程师，**本地部署**是刚需（工厂内网无法访问云服务）
- Electron 提供文件系统访问（导入 .ap18 工程文件）
- React 生态成熟，组件库丰富
- Tailwind 快速迭代 UI，无需维护 CSS 文件

**为什么不选**:
- Tauri: Rust 后端与 Python AI 生态不兼容，需要跨语言通信
- 纯 Web: 无法访问本地文件系统，知识库导入受限
- Qt/WPF: 开发效率低，UI 定制困难

---

## D-003: 向量数据库 → ChromaDB

**选择**: ChromaDB 0.5 (本地持久化)

**原因**:
- 零依赖部署：纯 Python，嵌入应用内，不需要独立服务器
- 内置嵌入模型（all-MiniLM-L6-v2），开箱即用
- 持久化到本地磁盘，重启不丢数据
- 对个人/小团队场景足够

**为什么不选**:
- Pinecone/Weaviate: 需要云服务或独立部署，违背"本地运行"原则
- FAISS: 没有内置持久化和元数据过滤
- PostgreSQL pgvector: 需要 PostgreSQL 实例，增加部署复杂度

**已知缺陷**:
- 默认嵌入模型 all-MiniLM-L6-v2 对中文支持差 → V1.1 计划换 BAAI/bge-m3

---

## D-004: 业务数据库 → SQLite

**选择**: SQLite 3 (WAL 模式)

**原因**:
- 零配置：随应用启动，无需安装数据库服务器
- 单用户场景完全够用（PLC 工程师个人工具）
- FTS5 扩展提供全文搜索能力
- 数据文件可直接备份/迁移

**为什么不选**:
- PostgreSQL: 需要独立安装和维护，个人工具不值得
- MongoDB: 数据结构明确（对话/项目/设置），不需要 schema-less
- Redis: 无持久化需求强到需要专门缓存层

**适用边界**:
- 如果未来做多用户/团队版，需要迁移到 PostgreSQL

---

## D-005: AI 模型策略 → 多模型 + 自动切换

**选择**: DeepSeek（主力）+ OpenAI / Kimi / Claude / 自定义（备选）

**原因**:
- DeepSeek V4 性价比最高，中文能力强，PLC 代码生成质量好
- 用户可能有不同模型的 API Key，不应锁死到一家
- 自动切换：主模型不可用时自动尝试下一个，避免用户操作中断

**为什么不选**:
- 只用 OpenAI: 中国用户访问不稳定
- 本地模型 (Ollama): PLC 代码生成需要强推理能力，7B/13B 效果不够
- 只用 Claude: 定价高，且需要 Anthropic SDK（与 OpenAI 兼容接口不同）

---

## D-006: 通信协议（运行态）→ S7 协议

**选择**: python-snap7（S7 协议）

**决策层级**: 这是父项目 (ai-plc-integration) 的决策，AI PLC Assistant 不直接连 PLC

**原因**:
- 兼容 PLCSIM Advanced + 真机
- 不需要 TIA 项目中启用 OPC UA
- 读写 DB/M/I/O 区，覆盖日常调试需求

**为什么不选**:
- OPC UA: PLCSIM 不提供 OPC UA 服务，仿真环境无法使用
- Modbus: 西门子 PLC 原生不支持 Modbus（需要额外 CM 模块）

---

## D-007: V1.0 不做 Agent / MCP / 运行态

**选择**: V1.0 定位为离线工程助手，不连接实时 PLC

**原因**:
- 一旦接入运行态 PLC，进入工业安全责任领域（停机风险、设备损坏）
- AI 直接控制 PLC 需要完整的安全链（互锁/影子仿真/双人确认/审计），V1.0 还不成熟
- 代码生成 + 知识库 + 工程复用的价值已经足够独立成产品
- Agent 编排需要稳定的基础功能支撑，V1.0 的测试覆盖刚刚建立

**何时重新评估**:
- V2.0，当以下条件满足时：
  - 115+ 测试持续绿灯
  - E2E 测试覆盖关键路径
  - 安全链代码经过实机验证
  - 至少 3-5 个真实 PLC 工程师试用反馈

---

## D-008: SSE 而非 WebSocket

**选择**: Server-Sent Events (POST /api/chat/stream)

**原因**:
- 单向流足够（服务端 → 客户端推 token）
- HTTP 协议，不需要额外连接管理
- FastAPI StreamingResponse 原生支持
- 兼容标准 fetch API + ReadableStream

**为什么不选**:
- WebSocket: 双向通信在此场景无必要，增加连接状态管理复杂度
- Long Polling: 延迟高，不适合逐 token 输出

---

## D-009: App.jsx 拆分策略 → Custom Hooks

**选择**: 5 个 custom hooks + 编排层 App.jsx

**原因**:
- React Hooks 是最轻量的状态拆分方式，不引入新依赖
- 每个 hook 职责单一，可独立测试和修改
- App.jsx 从 306 行降到 115 行，仅负责编排

**为什么不选**:
- Redux/Zustand: 项目规模不需要全局状态管理库
- Context Provider: 当前只有一层消费者，Context 是过度设计
- 拆分子组件而非 hooks: 状态逻辑和 UI 耦合度高，hooks 更适合

---

## D-010: 测试策略 → pytest + FastAPI TestClient

**选择**: pytest 单元测试 + API 集成测试，全局 Mock LLM

**原因**:
- pytest 是 Python 测试的事实标准
- FastAPI TestClient 提供零配置的 API 测试
- 全局 Mock LLM 避免消耗 API 额度且保证测试稳定性
- 115 测试在 11 秒内完成，CI 友好

**为什么不选**:
- 真实 LLM 调用测试: 不稳定、慢、费钱
- unittest: pytest 更简洁，fixture 更强大
- Playwright E2E: 延后到 V1.1（Electron 集成复杂度高，ROI 当前不如单元测试）

---

## D-011: 嵌入模型 → all-MiniLM-L6-v2（临时）

**选择**: ChromaDB 默认嵌入模型

**原因**:
- 零配置，ChromaDB 自动下载
- 英文文档检索效果可接受
- 384 维向量，资源消耗低

**已知问题**:
- 中文工业文档检索准确率低
- 不支持中文分词

**V1.1 迁移计划**:
- 换为 BAAI/bge-m3 或 bge-large-zh
- 需要重建向量索引（一次性操作）

---

## D-012: Prompt 模板持久化 → JSON 文件

**选择**: data/prompts.json 文件存储

**原因**:
- 9 个模板，读写频率极低
- JSON 可读可编辑，方便用户直接修改
- 不值得为此建 SQLite 表

**适用边界**:
- 如果模板数超过 100 个或需要多用户共享，迁移到 SQLite
