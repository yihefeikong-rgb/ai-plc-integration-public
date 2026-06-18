# TODO — AI 接入 PLC

> 生成时间：2026-06-18
> 交接时全面待办清单

---

## 高优先级（当前迭代必做）

### □ SVG 梯形图可视化
- **描述**: 将 LadderProgram.networks 数据渲染为 SVG 图形
- **文件**: `frontend/src/components/LadderVisualizer.jsx`（新建）
- **数据源**: `generator/__init__.py` 中的 `LadderProgram` 数据结构
- **验收**: 梯形图生成后展示 SVG 图形，非 ASCII 文本
- **估算**: 2-3 天

### □ Electron 打包验证
- **描述**: 运行 `npm run dist` 生成 NSIS 安装包并测试安装
- **检查项**:
  - `frontend/electron/main.js` 路径是否正确
  - `electron-builder` 配置（NSIS 语言/图标）
  - 打包后后端能否启动
  - 前端能访问后端 API
- **估算**: 1 天

### □ 后端 pytest 基础测试
- **描述**: 为 33 个 API 端点建立基础测试
- **文件**: `ai-plc-assistant/backend/tests/`（新建目录）
- **覆盖**: 核心路径（chat/stream, knowledge/import/search, generate/ladder）
- **mock**: 全局 Mock LLM（避免消耗 API 额度）
- **估算**: 2 天

### □ 统一版本号
- **描述**: 前后端版本号统一
- **文件**:
  - `backend/main.py` → `"version": "1.0.0"`
  - `frontend/package.json` → `"version": "1.0.0"`
- **估算**: 0.5 天

## 中优先级（V1.x 迭代）

### □ 知识库嵌入模型升级 (bge-m3)
- **原因**: all-MiniLM-L6-v2 中文支持差
- **操作**: 
  - 在 `config.py` 改 `embedding_model`
  - 删 `data/vector_db` 重建索引
  - 重新导入所有文档
- **风险**: 重建需要 15-30 分钟
- **估算**: 1 天

### □ 工程搜索中文分词
- **原因**: FTS5 LIKE 搜索性能低、准确率差
- **方案**: 引入 jieba 分词器
- **文件**: `search/indexer.py`、`search/__init__.py`
- **估算**: 1-2 天

### □ Playwright E2E 测试
- **原因**: 保障发布质量
- **路径**: 
  - 用户打开应用 → 看到 Dashboard
  - 选择模型 → 发送消息 → 看到回复
  - 导入文档 → 搜索知识库
- **估算**: 2 天

### □ 补全 SCL 模板（电梯/停车场/HVAC）
- **原因**: Deep Research 两次断流未完成
- **文件**: 已在工作区（新文件），需审查后提交
- **估算**: 1 天

### □ LLM 切换前端提示
- **原因**: 模型切换用户看不到
- **方案**: SSE 事件中携带 `fallback: true`，前端显示"已切换至 XX 模型"
- **估算**: 0.5 天

### □ SSE 对话后端完善
- **原因**: 当前 `/api/chat` 返回完整 JSON（非 SSE）
- **注意**: 前端已用 `/api/chat/stream`（SSE），通信层没问题
- **确认**: 检查 `/api/chat`（非 stream）是否还需要保留
- **估算**: 0.5 天

## 低优先级（V1.x 后续）

### □ 多语言界面
- 目前无海外用户需求
- 中/英切换

### □ 代码 Diff 视图
- 查看 AI 修改前后差异

### □ HMI 变量导入导出
- 工程流转闭环

### □ 前端 vitest 组件测试
- 保障 UI 稳定性

### □ 多轮 RAG 对话记忆
- 支持追问式检索

### □ 知识库侧栏文档分组
- 基础/进阶/行业三级（当前已有部分实现）

## V2.0 规划（暂不启动）

### □ TIA Openness 深度集成
- 条件: TiaWorker 稳定 + 测试覆盖

### □ AI Agent 直连 PLC 运行态
- 条件: 安全链经实机验证 + 3-5 用户反馈

### □ OPC UA MCP
- 运行时数据监控

### □ RBAC 权限控制
- 多用户场景

### □ 统一编排层 (Phase 5)
- 复杂任务自动拆解分配

---

## 待清理的文件

| 文件 | 操作 | 原因 |
|------|------|------|
| `research_*.txt` | 建议归档或删除 | Deep Research 中间结果 |
| `research_*.md` | 建议归档或删除 | 研究报告 |
| `check_openness.ps1` | 确认是否仍需 | 调试脚本 |
| `focus_plcsim.ps1` | 确认是否仍需 | 调试脚本 |
| `.coverage` | 建议删除 | 父项目生成，子项目未用 |
