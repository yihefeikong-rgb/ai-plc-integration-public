# API 契约 — AI 接入 PLC

> 这是 agent 开发时必须遵守的接口定义。完整版见项目根 `ARCHITECTURE.md` 第六节。

---

## AI PLC Assistant 后端 API（33 端点，端口 8005）

### 对话
- `POST /api/chat/stream` — SSE 流式对话（主入口）
- `POST /api/chat` — 非流式对话（备用）

### 模型
- `GET /api/models` — 模型列表
- `GET /api/models/{id}` — 模型详情
- `POST /api/settings/test/{provider}` — 测试连接

### 知识库
- `POST /api/knowledge/import` — 导入文档
- `GET /api/knowledge/search` — 向量搜索
- `GET /api/knowledge/documents` — 文档列表
- `DELETE /api/knowledge/documents/{id}` — 删除文档
- `GET /api/knowledge/status` — 统计
- `GET /api/knowledge/code-templates` — SCL 模板列表
- `GET /api/knowledge/code-templates/{name}` — SCL 模板内容
- `GET /api/knowledge/ladder-templates` — 梯形图模板列表
- `GET /api/knowledge/ladder-templates/{name}` — 梯形图模板详情

### 搜索
- `GET /api/search` — 工程搜索
- `POST /api/search/index` — 索引项目
- `GET /api/search/types` — 类型列表
- `GET /api/search/stats` — 统计
- `DELETE /api/search/index` — 清空索引

### 生成
- `POST /api/generate/ladder` — 梯形图生成
- `POST /api/generate/ladder/scl` — SCL 生成
- `POST /api/generate/ladder/xml` — XML 生成
- `POST /api/generate/export` — 代码导出
- `POST /api/generate/export/download` — 导出下载
- `POST /api/generate/prompt` — 调试 Prompt

### 模板
- `GET /api/prompts` — 模板列表
- `GET /api/prompts/categories` — 分类
- `GET /api/prompts/{id}` — 模板详情
- `POST /api/prompts` — 创建模板
- `PUT /api/prompts/{id}` — 更新模板
- `DELETE /api/prompts/{id}` — 删除模板

### 对话管理
- `GET /api/conversations` — 列表
- `POST /api/conversations` — 创建
- `GET /api/conversations/{id}` — 详情
- `PUT /api/conversations/{id}` — 更新
- `DELETE /api/conversations/{id}` — 删除
- `POST /api/conversations/{id}/messages` — 添加消息
- `GET /api/conversations/stats/overview` — 统计

### 项目
- `GET /api/projects` — 列表
- `POST /api/projects` — 创建
- `GET /api/projects/{id}` — 详情
- `PUT /api/projects/{id}` — 更新
- `DELETE /api/projects/{id}` — 删除
- `POST /api/projects/import` — 导入工程

### 设置
- `GET /api/settings` — 获取
- `PUT /api/settings` — 更新
- `GET /api/settings/providers` — 供应商列表

### 健康检查
- `GET /api/health` — 健康检查

---

## MCP 协议接口

### plc-mcp-bridge (65 tools)
- 工具前缀：`plc_` 和 `s7_`
- S7 运行态：connect/disconnect/read/write
- TIA 工程：块/DB/UDT/标签表/监控表的 CRUD + 编译/下载
- PLCSIM：创建/启动/停止/切换/状态
- Factory I/O：配置/启动/联动
- Pipeline：一键全流程

### tia-mcp
- 通过 JSON 临时文件与 TiaWorker.exe (C#) 通信
- TiaWorker 通过 TIA Openness DLL 操作 TIA Portal

---

## 响应格式

所有 API 响应遵循统一信封：
```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

SSE 事件格式：
```
data: {"type": "token", "content": "..."}
data: {"type": "done"}
data: {"type": "error", "message": "..."}
```