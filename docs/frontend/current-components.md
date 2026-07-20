# 当前组件清单

> 生成日期：2026-07-20
> Batch：1
> 范围：`ai-plc-assistant/frontend/src/components/` + `src/hooks/`

---

## 1. 组件总数

| 类型 | 数量 | 说明 |
|------|------|------|
| 业务页面组件 | 10 | Dashboard/ChatArea/LadderGenerator/CodeExplainer/FaultDiagnosis/IoTableGenerator/VariableAnalyzer/SettingsPanel/OrchestratorPanel/RobotPanel |
| 模板弹窗组件 | 3 | PromptTemplateModal/CodeTemplateModal/LadderTemplateModal |
| 对话框组件 | 1 | CreateProjectDialog |
| 布局组件 | 3 | Toolbar/Sidebar/ContextPanel/LogPanel（实为 4） |
| 通用组件 | 2 | ErrorBoundary/LadderVisualizer |
| Hooks | 6 | useTabs/useLogs/useModels/useProjects/useConversation/useWorkbenchHistory |

## 2. 业务页面组件

### 2.1 Dashboard.jsx (158 行)
- **Props**: `{ onOpenTab, onCreateProject }`
- **State**: projects/conversations/templates/health
- **API**: listProjects(5)/listConversations(5)/getTemplateCategories/orchestratorHealth
- **子组件**: 无（内联 quickActions/timeAgo）
- **特色**: 仅当 health 存在时显示系统状态卡片

### 2.2 ChatArea.jsx (271 行)
- **Props**: `{ messages, onSend, initialInput, sending }`
- **State**: input/showScrollBtn
- **API**: exportCode（导出 LadderResult）
- **子组件**: LadderResult / MessageBlock / LadderVisualizer
- **特色**: streaming 消息占位 + scroll-to-bottom 按钮 + LadderResult SVG/源码切换

### 2.3 LadderGenerator.jsx (320 行)
- **Props**: `{ addLog }`
- **State**: description/result/loading/pipelineLoading/pipelineResult/displayMode
- **API**: generateLadder/runNlToSim/exportCode
- **Hooks**: useWorkbenchHistory('ladder-generator')
- **子组件**: LadderVisualizer / PipelinePanel / formatDetail
- **特色**: 双按钮（生成 / 生成并仿真）+ 历史 select + SVG/源码切换

### 2.4 CodeExplainer.jsx (179 行)
- **Props**: `{ addLog }`
- **State**: code/language/result/loading/copied
- **API**: streamChat
- **Hooks**: useWorkbenchHistory('code-explainer')
- **特色**: 双栏（左代码 / 右 Markdown）+ 状态栏（字符/行/语言）

### 2.5 FaultDiagnosis.jsx (158 行)
- **Props**: `{ addLog }`
- **State**: symptoms/plcType/errorCode/result/loading/copied
- **API**: streamChat
- **Hooks**: useWorkbenchHistory('fault-diagnosis')
- **特色**: PLC 型号 select + 错误代码 input + 双栏

### 2.6 IoTableGenerator.jsx (135 行)
- **Props**: `{ addLog }`
- **State**: description/result/loading/copied
- **API**: streamChat
- **Hooks**: useWorkbenchHistory('io-table')
- **特色**: IO_PROMPT 内置匈牙利命名法要求 + 地址分配规则

### 2.7 VariableAnalyzer.jsx (131 行)
- **Props**: `{ addLog }`
- **State**: code/result/loading/copied
- **API**: streamChat
- **Hooks**: useWorkbenchHistory('variable-analyzer')
- **特色**: VARIABLE_PROMPT 要求按 I/Q/M/DB 分类 + 地址冲突检查

### 2.8 SettingsPanel.jsx (237 行)
- **Props**: `{ addLog }`
- **State**: form/providers/saving/saved/loading/testResults/testingId
- **API**: getSettings/updateSettings/getProviders/testProvider
- **子组件**: ProviderCard
- **Fallback**: FALLBACK_PROVIDERS 在后端不可用时显示
- **特色**: 测试连接前自动保存 form

### 2.9 OrchestratorPanel.jsx (871 行，最大文件)
- **Props**: `{ showTutorial, onCloseTutorial }`
- **State**: workflows/dynamicWfs/tools/servers/monitor/lastResult/running/loading/error/runDialog/editing/editorSteps/editorName/addStepOpen/stepServer/stepTool/stepParams/toolSearch/localTutorial
- **API**: fetch API_BASE + /orchestrator/*（直接 fetch，未走 api.js）
- **子组件**: StatCard / StepResultRow / ToolGroup / RunDialog / TutorialModal / Section / ToolCard / Step
- **中文映射**: WORKFLOW_CN/CATEGORY_CN/SERVER_CN/TOOL_CN（覆盖 65+15+7+6+3 工具）
- **特色**: 工作流编辑器（步骤增删/上下移/JSON 参数）+ 教程弹窗（6 章节）+ 工具搜索

### 2.10 RobotPanel.jsx (470 行)
- **Props**: `{}`（无 props）
- **State**: robot/logs/executing
- **API**: fetch API_BASE + /orchestrator/workflows/robot_pick_place/run
- **子组件**: RobotVisualization / CtrlBtn / SmBtn / StatusRow
- **常量**: INITIAL_STATE / MAX_LOGS
- **特色**: SVG 机械臂可视化 + 5 步拾取/放置序列动画 + 急停按钮（圆形大按钮）+ 自动循环降级本地模拟

## 3. 模板弹窗组件

### 3.1 PromptTemplateModal.jsx (162 行)
- **Props**: `{ onClose, onSelect }`
- **State**: templates/categories/activeCat/selected/varValues
- **API**: listTemplates/getTemplateCategories
- **布局**: 分类侧栏（136px） + 模板列表（224px） + 详情区
- **变量替换**: `{name}` → value

### 3.2 CodeTemplateModal.jsx (133 行)
- **Props**: `{ onClose }`
- **State**: templates/selected/content/ioData/loading/showScl
- **API**: listCodeTemplates/getCodeTemplateContent
- **子组件**: IoTable
- **特色**: SCL/文档切换 + IO 接口信号中文展示

### 3.3 LadderTemplateModal.jsx (105 行)
- **Props**: `{ onClose, onUseTemplate }`
- **State**: templates/selected/detail/loading
- **API**: listLadderTemplates/getLadderTemplate
- **特色**: ASCII-LAD 文本展示 + 复制 JSON + 使用模板（生成 prompt 跳转 chat）

## 4. 对话框组件

### 4.1 CreateProjectDialog.jsx (75 行)
- **Props**: `{ onSubmit, onCancel }`
- **State**: form `{ name, plcType, tiaVersion, language }`
- **常量**: PLC_TYPES/TIA_VERSIONS/LANGUAGES
- **键盘**: Enter 提交 / Esc 取消
- **样式**: 360px 宽，弹窗 + 3 列 select

## 5. 布局组件

### 5.1 Toolbar.jsx (171 行)
- **Props**: `{ models, selectedModel, onSelectModel, onMenuAction }`
- **State**: showModelMenu
- **子组件**: MenuDropdown
- **菜单**: 项目/编辑/工具/AI/视图/帮助（6 个菜单，22 个菜单项）
- **特色**: 7 个菜单项有快捷键标注（Ctrl+N/Z/Y/X/C/V/B/J/`）

### 5.2 Sidebar.jsx (217 行)
- **Props**: `{ onOpenTab, activeTab, addLog, onCreateProject, currentProject, conversations, currentConvId, onSwitchConversation, onDeleteConversation, onNewConversation, onOpenCodeTemplates, onOpenLadderTemplates }`
- **State**: projects/docs/uploading/deleteConfirm
- **API**: listProjects(20)/uploadDocument/listDocuments/deleteDocument
- **子组件**: Section / SidebarItem / DocGroup
- **Section**: 工程/对话/知识库/AI工具/设置（5 个）
- **aiTools 常量**: 7 个工具项（ladder/parse/diagnose/io-table/variables/orchestrator/robot）
- **特色**: DocGroup 按文件名数字前缀分组（1-3/4-10/11-99）+ 删除对话二次确认

### 5.3 ContextPanel.jsx (125 行)
- **Props**: `{ addLog, currentProject }`
- **State**: searchQuery/searchResults/searching
- **API**: searchProjects
- **子组件**: PanelSection
- **Section**: 当前工程/程序块/常用变量/工程搜索（4 个）
- **特色**: 工程搜索 + 结果列表（name/type/content 前 80 字符）

### 5.4 LogPanel.jsx (84 行)
- **Props**: `{ logs }`
- **State**: collapsed/activeTab
- **常量**: tabs `[{id:log,label:日志},{id:ai,label:AI调用}]`
- **特色**: 默认折叠 + Tab 切换 + 自动滚动到底

## 6. 通用组件

### 6.1 ErrorBoundary.jsx (50 行)
- **类组件**（React.Component）
- **Props**: `{ children }`
- **State**: hasError/error
- **特色**: 错误时显示 AlertTriangle + 错误消息 + stack 前 5 行 + 重试按钮

### 6.2 LadderVisualizer.jsx (184 行)
- **Props**: `{ networks }` 或 `{ code, networkTitle }`（兼容旧 API）
- **样式**: 内联 style，不依赖 Tailwind
- **常量**: COLORS（10 种元素类型色）
- **子组件**: Wire / Rail / ElementBox / RenderElement / RenderPath / RenderBranch / RenderRung
- **支持元素**: contact/coil/timer/counter/move/comparator/block_call/branch
- **特色**: 不解析 ASCII，由后端 ascii_parser.py 解析后传入结构化 LadderModel

## 7. Hooks

### 7.1 useTabs.js (42 行)
- **State**: tabs (默认 `[{id:welcome,closable:false}]`), activeTab
- **Methods**: openTab(id) / closeTab(id) / setActiveTab(id)
- **常量**: TAB_LABELS (10 个 tab 中文标签)

### 7.2 useLogs.js (14 行)
- **State**: logs (默认 1 条 "系统已启动")
- **Methods**: addLog(level, message)
- **level**: info/warn/error

### 7.3 useModels.js (20 行)
- **State**: models (默认 DeepSeek), selectedModel
- **API**: getModels
- **特色**: 自动选择第一个 enabled 的模型

### 7.4 useProjects.js (39 行)
- **State**: currentProject, importRef
- **API**: createProject/importProject
- **Methods**: handleCreateProject(data) / handleImportProject(e)
- **默认值**: plcType=S7-1200, tiaVersion=V18, language=SCL

### 7.5 useConversation.js (206 行)
- **State**: convId/conversations/messages/sending/pendingInput/streamContentRef
- **API**: createConversation/addMessage/getConversation/listConversations/deleteConversation/generateLadder/streamChat
- **Methods**: handleNewConversation/handleSwitchConversation/handleDeleteConversation/handleSend/refreshConversations
- **关键逻辑**: isGenerationRequest 判断（梯形图/ladder 关键字走非流式，其他走 SSE）
- **回退**: SSE 失败 → 非流式 fetch /api/chat
- **上下文**: currentProject 转为 project_context 传给后端

### 7.6 useWorkbenchHistory.js (43 行)
- **State**: history (localStorage 持久化)
- **Methods**: save(entry) / remove(id) / clear()
- **参数**: key, maxItems=20
- **localStorage key**: `wb_history_${key}`

## 8. 组件依赖关系

```
App.jsx
  ├─ ErrorBoundary
  ├─ Toolbar (models/useModels)
  ├─ Sidebar (listProjects/uploadDocument/listDocuments/deleteDocument/listConversations)
  ├─ Dashboard (listProjects/listConversations/getTemplateCategories/orchestratorHealth)
  ├─ ChatArea
  │   └─ LadderVisualizer
  ├─ ContextPanel (searchProjects)
  ├─ LogPanel
  ├─ PromptTemplateModal (listTemplates/getTemplateCategories)
  ├─ CodeTemplateModal (listCodeTemplates/getCodeTemplateContent)
  ├─ LadderTemplateModal (listLadderTemplates/getLadderTemplate)
  ├─ SettingsPanel (getSettings/updateSettings/getProviders/testProvider)
  ├─ CodeExplainer (streamChat)
  ├─ IoTableGenerator (streamChat)
  ├─ FaultDiagnosis (streamChat)
  ├─ LadderGenerator (generateLadder/runNlToSim/exportCode + LadderVisualizer)
  ├─ VariableAnalyzer (streamChat)
  ├─ CreateProjectDialog
  ├─ OrchestratorPanel (fetch /orchestrator/*)
  └─ RobotPanel (fetch /orchestrator/workflows/robot_pick_place/run)
```

## 9. 文件大小排序（行数）

| 文件 | 行数 | 备注 |
|------|------|------|
| OrchestratorPanel.jsx | 871 | 最大，含编辑器+教程 |
| RobotPanel.jsx | 470 | SVG 可视化 |
| LadderGenerator.jsx | 320 | 双模式生成 |
| ChatArea.jsx | 271 | 消息流+Ladder |
| Sidebar.jsx | 217 | 5 Section |
| useConversation.js | 206 | SSE+回退 |
| LadderVisualizer.jsx | 184 | SVG 梯形图 |
| CodeExplainer.jsx | 179 | 双栏代码解析 |
| PromptTemplateModal.jsx | 162 | 模板选择 |
| Dashboard.jsx | 158 | 首页 |
| FaultDiagnosis.jsx | 158 | 故障诊断 |
| Toolbar.jsx | 171 | 菜单+模型 |
| IoTableGenerator.jsx | 135 | IO 表 |
| VariableAnalyzer.jsx | 131 | 变量分析 |
| ContextPanel.jsx | 125 | Inspector |
| CodeTemplateModal.jsx | 133 | SCL 模板 |
| LadderTemplateModal.jsx | 105 | LAD 模板 |
| LogPanel.jsx | 84 | 底部面板 |
| CreateProjectDialog.jsx | 75 | 新建项目 |
| ErrorBoundary.jsx | 50 | 错误兜底 |
| useTabs.js | 42 | Tab 路由 |
| useProjects.js | 39 | 项目 |
| useWorkbenchHistory.js | 43 | 历史 |
| useModels.js | 20 | 模型 |
| useLogs.js | 14 | 日志 |

## 10. 组件质量评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 单文件大小 | 中 | OrchestratorPanel 871 行超 800 阈值，需拆分 |
| 复用性 | 低 | 无基础组件库，按钮/输入/面板各自实现 |
| 一致性 | 中 | Tailwind ide.* 类名一致，但 3 个 Modal 用 `bg-surface` 未定义类名 |
| 可访问性 | 低 | 多数按钮无 aria-label，弹窗无 focus trap |
| 测试覆盖 | 极低 | 仅 LadderGenerator 有 2 个测试 |
| TypeScript | 无 | 全部 .jsx，无类型注解 |
