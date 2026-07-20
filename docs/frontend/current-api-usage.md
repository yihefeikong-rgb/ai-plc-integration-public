# 当前 API 使用梳理

> 生成日期：2026-07-20
> Batch：1
> 范围：`ai-plc-assistant/frontend/src/api.js` + 组件内直接 fetch

---

## 1. API 客户端

### 1.1 基础配置 (api.js)

```js
export const API_BASE = import.meta.env.DEV ? '/api' : 'http://127.0.0.1:8005/api'
const LOCAL_API_TOKEN = import.meta.env.VITE_LOCAL_API_TOKEN

export function localControlHeaders() {
  return LOCAL_API_TOKEN ? { 'X-Local-Api-Token': LOCAL_API_TOKEN } : {}
}
```

**问题**：
- 生产模式硬编码 `http://127.0.0.1:8005`，无法环境变量覆盖
- `LOCAL_API_TOKEN` 通过 `import.meta.env` 注入，构建时硬编码到 bundle

### 1.2 请求封装

```js
async function request(path, options = {}) {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const headers = { ...localControlHeaders(), ...options.headers }
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData
  if (!isFormData && !headers['Content-Type']) headers['Content-Type'] = 'application/json'
  const res = await fetch(url, { ...options, headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}
```

**特性**：
- 自动添加 `X-Local-Api-Token` header
- FormData 自动跳过 Content-Type
- 错误时抛出 Error(detail || HTTP {status})

### 1.3 SSE 流式

```js
export async function streamChat({ model_id, messages, temperature, project_context, onToken, onDone, onError, signal }) {
  // fetch + ReadableStream + TextDecoder
  // 解析 SSE 格式: data: {json}
  // [DONE] 结束
  // 支持 token/error/rag_sources/done
}
```

## 2. API 端点清单（按模块）

### 2.1 项目管理 (5 个)

| 函数 | 方法 | 路径 | 用途 |
|------|------|------|------|
| `listProjects(limit=50)` | GET | `/projects?limit={limit}` | 项目列表 |
| `getProject(id)` | GET | `/projects/{id}` | 项目详情 |
| `createProject(data)` | POST | `/projects` | 创建项目 |
| `updateProject(id, data)` | PUT | `/projects/{id}` | 更新项目 |
| `deleteProject(id)` | DELETE | `/projects/{id}` | 删除项目 |
| `importProject(file)` | POST | `/projects/import` (FormData) | 导入工程 |

**调用方**：
- useProjects.handleCreateProject → createProject
- useProjects.handleImportProject → importProject
- Sidebar useEffect → listProjects(20)
- Dashboard useEffect → listProjects(5)

### 2.2 对话管理 (5 个)

| 函数 | 方法 | 路径 | 用途 |
|------|------|------|------|
| `listConversations(limit=20)` | GET | `/conversations?limit={limit}` | 对话列表 |
| `getConversation(id)` | GET | `/conversations/{id}` | 对话详情（含消息） |
| `createConversation(title, model_id)` | POST | `/conversations` | 创建对话 |
| `deleteConversation(id)` | DELETE | `/conversations/{id}` | 删除对话 |
| `addMessage(convId, role, content, msg_type, metadata)` | POST | `/conversations/{convId}/messages` | 添加消息 |

**调用方**：useConversation hook

### 2.3 知识库 (5 个)

| 函数 | 方法 | 路径 | 用途 |
|------|------|------|------|
| `uploadDocument(file)` | POST | `/knowledge/import` (FormData) | 上传文档 |
| `searchKnowledge(query, limit=5)` | GET | `/knowledge/search?q=&limit=` | 知识库搜索 |
| `getKnowledgeStatus()` | GET | `/knowledge/status` | 知识库状态 |
| `listDocuments()` | GET | `/knowledge/documents` | 文档列表 |
| `deleteDocument(id)` | DELETE | `/knowledge/documents/{id}` | 删除文档 |

**调用方**：Sidebar（listDocuments/uploadDocument/deleteDocument）

### 2.4 PLC 工程搜索 (3 个)

| 函数 | 方法 | 路径 | 用途 |
|------|------|------|------|
| `searchProjects(query, typeFilter, limit=20)` | GET | `/search?q=&type_filter=&limit=` | 工程搜索 |
| `getSearchStats()` | GET | `/search/stats` | 搜索统计 |
| `indexProjectDir(directory)` | POST | `/search/index?directory=` | 索引项目目录 |

**调用方**：ContextPanel.handleSearch → searchProjects

### 2.5 梯形图生成 (3 个)

| 函数 | 方法 | 路径 | 用途 |
|------|------|------|------|
| `generateLadder(input, variables, templateId, modelId)` | POST | `/generate/ladder` | 生成梯形图 |
| `generateSCL(input)` | POST | `/generate/ladder/scl` | 生成 SCL |
| `exportCode(data)` | POST | `/generate/export` | 导出 SCL/XML/CSV/HMI |

**调用方**：
- useConversation.handleSend → generateLadder（梯形图关键字时）
- LadderGenerator.handleGenerate → generateLadder
- ChatArea.handleExport / LadderGenerator.doExport → exportCode

### 2.6 全链路 Pipeline (1 个)

| 函数 | 方法 | 路径 | 用途 |
|------|------|------|------|
| `runNlToSim(payload)` | POST | `/pipeline/nl-to-sim` | NL → 生成 → 编译 → 下载 → PLCSIM 仿真 |

**调用方**：LadderGenerator.handleRunPipeline

### 2.7 Prompt 模板 (3 个)

| 函数 | 方法 | 路径 | 用途 |
|------|------|------|------|
| `listTemplates(category)` | GET | `/prompts?category=` | 模板列表 |
| `getTemplate(id)` | GET | `/prompts/{id}` | 模板详情 |
| `getTemplateCategories()` | GET | `/prompts/categories` | 分类列表 |

**调用方**：PromptTemplateModal / Dashboard

### 2.8 设置 (4 个)

| 函数 | 方法 | 路径 | 用途 |
|------|------|------|------|
| `getSettings()` | GET | `/settings` | 获取设置 |
| `updateSettings(data)` | PUT | `/settings` | 更新设置 |
| `getProviders()` | GET | `/settings/providers` | 模型 Provider 列表 |
| `testProvider(provider)` | POST | `/settings/test/{provider}` | 测试 Provider 连接 |

**调用方**：SettingsPanel

### 2.9 模型 (1 个)

| 函数 | 方法 | 路径 | 用途 |
|------|------|------|------|
| `getModels()` | GET | `/models` | 模型列表 |

**调用方**：useModels

### 2.10 SSE 流式对话 (1 个)

| 函数 | 方法 | 路径 | 用途 |
|------|------|------|------|
| `streamChat({model_id, messages, temperature, project_context, onToken, onDone, onError, signal})` | POST | `/chat/stream` (SSE) | 流式对话 |

**调用方**：
- useConversation.handleSend
- CodeExplainer.handleExplain
- IoTableGenerator.handleGenerate
- FaultDiagnosis.handleDiagnose
- VariableAnalyzer.handleAnalyze

### 2.11 代码模板 (2 个)

| 函数 | 方法 | 路径 | 用途 |
|------|------|------|------|
| `listCodeTemplates()` | GET | `/knowledge/code-templates` | SCL 模板列表 |
| `getCodeTemplateContent(name)` | GET | `/knowledge/code-templates/{name}` | 模板内容 |

**调用方**：CodeTemplateModal

### 2.12 梯形图模板 (2 个)

| 函数 | 方法 | 路径 | 用途 |
|------|------|------|------|
| `listLadderTemplates()` | GET | `/knowledge/ladder-templates` | 模板列表 |
| `getLadderTemplate(name)` | GET | `/knowledge/ladder-templates/{name}` | 模板详情 |

**调用方**：LadderTemplateModal

### 2.13 健康检查 (1 个)

| 函数 | 方法 | 路径 | 用途 |
|------|------|------|------|
| `healthCheck()` | GET | `/health` | 后端健康检查 |

**调用方**：未在组件中使用（仅 api.js 导出）

### 2.14 编排层 (6 个)

| 函数 | 方法 | 路径 | 用途 |
|------|------|------|------|
| `orchestratorHealth()` | GET | `/orchestrator/health` | 编排层健康 |
| `listWorkflows()` | GET | `/orchestrator/workflows` | 工作流列表 |
| `runWorkflow(name, input)` | POST | `/orchestrator/workflows/{name}/run` | 运行工作流 |
| `listOrchestratorTools()` | GET | `/orchestrator/tools` | 工具列表 |
| `listServers()` | GET | `/orchestrator/servers` | 服务器列表 |
| `getMonitor()` | GET | `/orchestrator/monitor` | 监控数据 |

**调用方**：
- Dashboard → orchestratorHealth
- OrchestratorPanel（直接 fetch，未用 api.js 函数）
- RobotPanel（直接 fetch robot_pick_place/run）

### 2.15 OrchestratorPanel 直接 fetch（未走 api.js）

| 路径 | 方法 | 用途 |
|------|------|------|
| `/orchestrator/workflows/dynamic` | GET | 动态工作流列表 |
| `/orchestrator/workflows/dynamic` | POST | 保存动态工作流 |
| `/orchestrator/workflows/dynamic/{name}` | DELETE | 删除动态工作流 |
| `/orchestrator/workflows/adhoc` | POST | 临时执行步骤 |
| `/orchestrator/workflows/{name}/run` | POST | 运行工作流（与 api.js 重复） |

**问题**：OrchestratorPanel 重新封装了 apiGet/apiPost/apiDelete，未复用 api.js 的 request 函数。

### 2.16 RobotPanel 直接 fetch

| 路径 | 方法 | 用途 |
|------|------|------|
| `/orchestrator/workflows/robot_pick_place/run` | POST | 调用机器人工作流 |

**问题**：未复用 api.js 的 `runWorkflow` 函数。

### 2.17 useConversation 直接 fetch（SSE 回退）

| 路径 | 方法 | 用途 |
|------|------|------|
| `/chat` | POST | SSE 失败时回退非流式对话 |

## 3. API 调用统计

| 模块 | 端点数 | 调用组件 |
|------|--------|---------|
| 项目管理 | 6 | useProjects/Sidebar/Dashboard |
| 对话管理 | 5 | useConversation |
| 知识库 | 5 | Sidebar |
| 工程搜索 | 3 | ContextPanel |
| 梯形图生成 | 3 | LadderGenerator/useConversation/ChatArea |
| 全链路 Pipeline | 1 | LadderGenerator |
| Prompt 模板 | 3 | PromptTemplateModal/Dashboard |
| 设置 | 4 | SettingsPanel |
| 模型 | 1 | useModels |
| SSE 对话 | 1 | useConversation/4 个 AI 工具页 |
| 代码模板 | 2 | CodeTemplateModal |
| 梯形图模板 | 2 | LadderTemplateModal |
| 健康检查 | 1 | (未使用) |
| 编排层 | 6 + 5 (Panel 内) | Dashboard/OrchestratorPanel/RobotPanel |
| **总计** | **48** | |

## 4. 端口与代理

### 4.1 开发模式
- Vite dev server: `localhost:5173`
- Vite proxy: `/api` → `http://127.0.0.1:8005`
- 后端 FastAPI: `127.0.0.1:8005`

### 4.2 生产模式（Web）
- 静态部署：`dist/` 目录
- API 直连：`http://127.0.0.1:8005/api`（硬编码，无法配置）
- CORS：需后端配置允许前端域名

### 4.3 生产模式（Electron）
- 加载 `dist/index.html`
- API 直连：同上

## 5. Web 兼容性问题

| 问题 | 影响 | Batch 2 修复 |
|------|------|------|
| API_BASE 硬编码 | Web 部署到非本机后端无法配置 | 改为 `import.meta.env.VITE_API_BASE \|\| '/api'` |
| `window.open('http://127.0.0.1:8005/docs')` | Web 部署后失效 | 改为相对路径 `/docs` 或环境变量 |
| CSP `connect-src 'self' http://localhost:*` | 限制 WebSocket/EventSource 到 localhost | Web 部署需调整 CSP |
| SSE 用 fetch + ReadableStream | 浏览器原生支持，Web 兼容 | 无需修改 |
| FormData 文件上传 | 浏览器原生支持，Web 兼容 | 无需修改 |
| Blob 下载 | 浏览器原生支持，Web 兼容 | 无需修改 |
| localStorage 历史记录 | 浏览器原生支持，Web 兼容 | 无需修改 |

## 6. 安全注意事项

### 6.1 Token 处理
- `VITE_LOCAL_API_TOKEN` 通过 `import.meta.env` 注入，构建时硬编码到 bundle
- **风险**：Token 出现在 JS bundle 中，任何人可查看
- **建议**：Web 模式不注入 Token，依赖后端代理或 Same-Origin Cookie

### 6.2 API Key 处理
- SettingsPanel `type="password"` 输入，UI 隐藏
- `getSettings()` 返回后端存储的 API Key，前端可读
- **风险**：API Key 出现在网络响应中，可能被截获
- **建议**：后端返回时脱敏（如 `sk-***`），前端仅展示掩码

### 6.3 测试连接结果
- `testProvider` 返回 `{status, message, reply}`
- `reply` 字段是模型回复，可能包含敏感信息
- **风险**：reply 展示在 UI，可能出现在截图
- **建议**：测试连接 reply 仅在 dev 模式展示

## 7. 建议

### 7.1 Batch 2 改造
1. `API_BASE` 改为环境变量优先：`import.meta.env.VITE_API_BASE || '/api'`
2. 添加 `.env.example` / `.env.development` / `.env.production.example`
3. 建立 `src/platform/runtime.js` 提供 `isElectron()/isWeb()/getRuntimeMode()`
4. `window.open` API 文档地址改为相对路径或环境变量

### 7.2 后续 Batch 改造
1. OrchestratorPanel/RobotPanel 复用 api.js 的 request 函数，消除直接 fetch
2. 编排层动态工作流 API 函数加入 api.js（`listDynamicWorkflows/saveDynamicWorkflow/deleteDynamicWorkflow/runAdhoc`）
3. 健康检查 `healthCheck` 在 Dashboard 显示后端状态
4. SSE 加入 `onStart/onProgress` 回调，支持任务进度展示
