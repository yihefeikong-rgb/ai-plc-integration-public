# API 契约（当前实现快照）

> 本文件是 2026-07-13 的人工同步摘要。运行中的 FastAPI `/openapi.json` 是端点、请求模型和响应模型的唯一机器可读来源；不得再假设所有 API 使用统一 `success/data/error` 信封。

## 地址与鉴权

- 后端绑定：`127.0.0.1:8005`；开发前端通过 Vite 的 `/api` 代理访问同一端口。
- 根目录 `start.bat` 只启动后端；后端内嵌的编排层是 MCP stdio 子进程的唯一生命周期所有者。独立 `orchestrator.api` 仅可作为诊断进程单独运行，若已有所有者会因 `AI_PLC_MCP_OWNER_LOCK` 失败关闭。
- 健康检查：`GET /api/health` 返回 `{"status":"ok","version":"1.0.0"}`。
- 控制面：已受保护的端点必须带 `X-Local-Api-Token`，其值与 `LOCAL_API_TOKEN` 一致；未配置令牌返回 `503`，缺失或错误令牌返回 `401`。
- FastAPI 参数校验失败返回 `422`，错误体为 `{"detail":"..."}`；未捕获错误返回 `500`，同样使用 `detail` 字段。

## 路由分组

| 前缀 | 当前端点类型 | 鉴权 |
|---|---|---|
| `/api/chat` | `POST /`、`POST /stream` | 是 |
| `/api/knowledge` | 导入、检索、文档、统计、SCL/LAD 模板 | 是 |
| `/api/search` | 查询、索引、类型、统计、清空索引 | 是 |
| `/api/projects` | 项目 CRUD、受限 zip 导入 | 是 |
| `/api/generate` | LAD/SCL/XML 生成、导出、提示词预览 | 是 |
| `/api/pipeline/nl-to-sim` | 受控 NL→模拟流程 | 是 |
| `/api/orchestrator` | 健康、工作流、工具、服务器、监控、动态工作流、确认令牌 | 写入/执行端点是；只读发现端点当前未要求令牌 |
| `/api/settings` | 获取、更新、提供商列表、连通性测试 | 更新与测试是；只读端点当前未要求令牌 |
| `/api/models` | 模型列表与详情 | 当前未要求令牌 |
| `/api/prompts` | Prompt 模板 CRUD | 当前未要求令牌 |
| `/api/conversations` | 对话历史 CRUD 与统计 | 当前未要求令牌 |

## 关键响应语义

- 编排执行返回 `workflow_name`、顶层 `ok`、逐步骤 `steps[]`、可选 `error` 与 `total_duration_ms`。调用方必须同时检查顶层和每个步骤的 `ok`，不得只以 HTTP 200 视为成功。
- 聊天 SSE 使用 `data: <JSON>`；令牌为 `token`，完成事件带 `done`，错误事件带 `error`，可选 RAG 来源为 `rag_sources`。
- 文件导入、索引与生成接口的成功响应由各路由的 Pydantic/字典模型直接给出；前端必须检查 HTTP 状态和该路由声明的字段，不能假设统一包装。
- 写入确认由 `POST /api/orchestrator/confirmations` 签发，成功返回 `confirmation_token` 和 `audit_id`；令牌不是写入成功证明，最终写入边界仍会校验其绑定目标、值、设备、操作者和一次性状态。

## 变更规则

修改路由、响应模型、鉴权依赖或端口时，必须同时更新本文件并以离线 API 测试验证。不得把历史文档中的“33 端点”“端口 8005/8000/8001”混用为当前契约。
