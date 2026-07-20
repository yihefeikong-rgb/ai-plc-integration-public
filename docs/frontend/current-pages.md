# 当前页面清单

> 生成日期：2026-07-20
> Batch：1
> 范围：`ai-plc-assistant/frontend/src/`

---

## 1. Tab 路由模型

当前前端无 URL 路由，使用 `useTabs` 内部状态管理：
- `tabs` 数组保存已打开的 Tab
- `activeTab` 保存当前激活 Tab id
- `openTab(id)` 加入并激活
- `closeTab(id)` 移除并回到最后一个

Tab 切换通过 `display: none` 保持挂载，避免状态丢失。

## 2. 页面清单（10 个）

| Tab ID | 中文标签 | 组件 | 文件 | 用途 | 关键状态 |
|--------|---------|------|------|------|---------|
| `welcome` | 欢迎 | Dashboard | `components/Dashboard.jsx` | 首页总览 | 默认打开，不可关闭 |
| `chat` | AI 助手 | ChatArea | `components/ChatArea.jsx` | AI 对话 + Ladder 结果展示 | convId/messages/sending/pendingInput |
| `ladder` | 梯形图生成 | LadderGenerator | `components/LadderGenerator.jsx` | NL→梯形图 + 全链路仿真 | description/result/pipelineResult/displayMode |
| `parse` | 程序解析 | CodeExplainer | `components/CodeExplainer.jsx` | PLC 代码 AI 解析 | code/language/result |
| `diagnose` | 故障诊断 | FaultDiagnosis | `components/FaultDiagnosis.jsx` | AI 故障诊断 | symptoms/plcType/errorCode/result |
| `io-table` | IO表生成 | IoTableGenerator | `components/IoTableGenerator.jsx` | NL→IO 表 | description/result |
| `variables` | 变量分析 | VariableAnalyzer | `components/VariableAnalyzer.jsx` | PLC 代码变量提取分析 | code/result |
| `settings` | 设置 | SettingsPanel | `components/SettingsPanel.jsx` | 模型 API + PLC 默认配置 | form/providers/testResults |
| `orchestrator` | 编排管理 | OrchestratorPanel | `components/OrchestratorPanel.jsx` | 工作流/工具/服务器管理 | workflows/tools/servers/monitor |
| `robot` | 机器人 | RobotPanel | `components/RobotPanel.jsx` | 机器人模拟控制 | robot/logs/executing |

## 3. 弹窗（6 个，不入 Tab）

| 弹窗 | 触发位置 | 组件 | 状态 |
|------|---------|------|------|
| PromptTemplateModal | Toolbar 菜单/AI/Sidebar/Dashboard | `components/PromptTemplateModal.jsx` | showTemplates (App.jsx) |
| CodeTemplateModal | Sidebar 知识库/SCL代码模板 | `components/CodeTemplateModal.jsx` | showCodeTemplate (App.jsx) |
| LadderTemplateModal | Sidebar 知识库/梯形图模板 | `components/LadderTemplateModal.jsx` | showLadderTemplate (App.jsx) |
| CreateProjectDialog | Toolbar 菜单/项目/Sidebar/Dashboard | `components/CreateProjectDialog.jsx` | showCreateDialog (App.jsx) |
| About | Toolbar 菜单/帮助/关于 | 内联 App.jsx | showAbout (App.jsx) |
| OrchestratorTutorial | Toolbar 菜单/帮助/OrchestratorPanel 教程按钮 | 内联 OrchestratorPanel.jsx | showOrchTutorial (App.jsx) + localTutorial (OrchestratorPanel) |

## 4. 页面详情

### 4.1 welcome (Dashboard)
- **入口**：默认打开
- **布局**：`flex-1 overflow-y-auto p-8 max-w-4xl mx-auto`
- **区块**：
  1. Header: "欢迎回来" + 副标题
  2. Quick Actions: 4 个卡片（梯形图/解析/IO表/诊断）
  3. System Status: 仅当 `health` 存在时显示，1 行 3 指标
  4. Recent Projects: listProjects(5) 列表
  5. Recent Conversations: listConversations(5) 列表（仅当 > 0）
  6. Templates: getTemplateCategories() 标签云
- **API 调用**：listProjects / listConversations / getTemplateCategories / orchestratorHealth
- **空状态**：暂无项目，点击上方"新建项目"开始

### 4.2 chat (ChatArea)
- **入口**：Toolbar AI/新建对话 + Sidebar 对话/新建对话 + 模板选择后跳转
- **布局**：消息流 + 底部输入栏
- **消息类型**：
  - user: 纯文本
  - assistant: ReactMarkdown 渲染
  - assistant type='ladder': LadderResult 组件（标题/变量表/网络/导出）
- **输入区**：单行 input + 发送按钮，无附件/模板/模型选择
- **SSE**：streamChat 调用，streaming=true 时占位消息
- **API**：streamChat / exportCode（导出） / addMessage（持久化）

### 4.3 ladder (LadderGenerator)
- **入口**：Sidebar AI工具/梯形图生成 + Dashboard 快捷操作
- **布局**：标题栏 + 历史栏（条件） + 结果区 + 底部输入栏
- **状态**：description/result/loading/pipelineLoading/displayMode('graph'|'source')
- **API**：generateLadder / runNlToSim / exportCode
- **历史**：useWorkbenchHistory('ladder-generator')，最多 20 条
- **可视化**：LadderVisualizer（SVG）或源码 pre
- **导出**：SCL/XML/CSV/HMI

### 4.4 parse (CodeExplainer)
- **入口**：Sidebar AI工具/程序解析 + Dashboard 快捷操作
- **布局**：左代码输入 + 右结果，双栏
- **状态**：code/language/result/loading
- **API**：streamChat
- **历史**：useWorkbenchHistory('code-explainer')
- **支持语言**：SCL/LAD/STL/FBD/auto

### 4.5 diagnose (FaultDiagnosis)
- **入口**：Sidebar AI工具/故障诊断 + Dashboard 快捷操作
- **布局**：左输入（PLC型号/错误代码/故障描述） + 右结果
- **状态**：symptoms/plcType/errorCode/result/loading
- **API**：streamChat
- **历史**：useWorkbenchHistory('fault-diagnosis')

### 4.6 io-table (IoTableGenerator)
- **入口**：Sidebar AI工具/IO表生成 + Dashboard 快捷操作
- **布局**：左输入（设备描述） + 右 Markdown 表格
- **状态**：description/result/loading
- **API**：streamChat
- **历史**：useWorkbenchHistory('io-table')

### 4.7 variables (VariableAnalyzer)
- **入口**：Sidebar AI工具/变量分析
- **布局**：左代码 + 右 Markdown 表格
- **状态**：code/result/loading
- **API**：streamChat
- **历史**：useWorkbenchHistory('variable-analyzer')

### 4.8 settings (SettingsPanel)
- **入口**：Sidebar 设置/模型配置 + Toolbar 项目/项目设置
- **布局**：标题栏 + 保存按钮 + 5 Provider 卡片 + PLC 默认配置
- **状态**：form/providers/saving/saved/loading/testResults/testingId
- **API**：getSettings/updateSettings/getProviders/testProvider
- **Fallback**：FALLBACK_PROVIDERS 在后端不可用时显示

### 4.9 orchestrator (OrchestratorPanel)
- **入口**：Sidebar AI工具/编排管理
- **布局**：顶栏 + 错误提示 + 3 状态卡片 + 工作流编辑器（条件）+ 工作流列表 + 工具列表 + 执行结果 + 监控
- **状态**：workflows/dynamicWfs/tools/servers/monitor/lastResult/running/loading/error/runDialog/editing
- **API**：API_BASE + /orchestrator/* （通过 fetch 直接调用）
- **特色**：中文映射表 WORKFLOW_CN/CATEGORY_CN/SERVER_CN/TOOL_CN

### 4.10 robot (RobotPanel)
- **入口**：Sidebar AI工具/机器人
- **布局**：标题栏 + SVG 可视化 + 手动控制 + 急停 + 状态信息 + 操作日志
- **状态**：robot/logs/executing
- **API**：API_BASE + /orchestrator/workflows/robot_pick_place/run
- **模拟**：所有动作 setTimeout 模拟，无真实 PLC 通信

## 5. 页面间跳转关系

```
welcome
  ├─→ ladder (Quick Action)
  ├─→ parse (Quick Action)
  ├─→ io-table (Quick Action)
  ├─→ diagnose (Quick Action)
  ├─→ project (Sidebar 项，setCurrentProject)
  ├─→ chat (Recent Conversation)
  ├─→ templates (PromptTemplateModal)
  └─→ project:new (CreateProjectDialog)

chat
  ├─→ templates (PromptTemplateModal via Sidebar)
  └─→ chat (模板选择后 setPendingInput)

Sidebar
  ├─→ ladder/parse/diagnose/io-table/variables/orchestrator/robot
  ├─→ templates (PromptTemplateModal)
  ├─→ CodeTemplateModal
  ├─→ LadderTemplateModal
  ├─→ project (setCurrentProject)
  └─→ settings

Toolbar 菜单
  ├─→ project:new / project:import / project:settings
  ├─→ tool:ladder / tool:parse / tool:io-table / tool:variables / tool:diagnose / tool:search / tool:index
  ├─→ ai:new-chat / ai:templates / ai:knowledge
  ├─→ view:sidebar / view:context / view:bottom
  └─→ help:about / help:api-docs / help:orchestrator-tutorial
```

## 6. Tab 标签常量

`useTabs.js` 的 `TAB_LABELS`：
```js
{
  welcome: '欢迎',
  chat: 'AI 助手',
  ladder: '梯形图生成',
  parse: '程序解析',
  diagnose: '故障诊断',
  'io-table': 'IO表生成',
  variables: '变量分析',
  settings: '设置',
  orchestrator: '编排管理',
  robot: '机器人',
}
```

## 7. 截图清单（主计划 Batch 1 要求 14 个）

| # | 页面 | 已截图 | 文件名 |
|---|------|--------|--------|
| 1 | dashboard (welcome) | 待生成 | dashboard-1366x768.png / dashboard-1920x1080.png |
| 2 | chat | 待生成 | chat-1366x768.png / chat-1920x1080.png |
| 3 | ladder-generator | 待生成 | ladder-1366x768.png / ladder-1920x1080.png |
| 4 | program-parser (parse) | 待生成 | parse-1366x768.png / parse-1920x1080.png |
| 5 | io-table | 待生成 | io-table-1366x768.png / io-table-1920x1080.png |
| 6 | variable-analyzer | 待生成 | variables-1366x768.png / variables-1920x1080.png |
| 7 | fault-diagnosis | 待生成 | diagnose-1366x768.png / diagnose-1920x1080.png |
| 8 | orchestrator | 待生成 | orchestrator-1366x768.png / orchestrator-1920x1080.png |
| 9 | robot | 待生成 | robot-1366x768.png / robot-1920x1080.png |
| 10 | settings | 待生成 | settings-1366x768.png / settings-1920x1080.png |
| 11 | prompt-template-modal | 待生成 | prompt-template-modal-1366x768.png |
| 12 | code-template-modal | 待生成 | code-template-modal-1366x768.png |
| 13 | ladder-template-modal | 待生成 | ladder-template-modal-1366x768.png |
| 14 | create-project-dialog | 待生成 | create-project-dialog-1366x768.png |

截图存入 `docs/frontend/screenshots/before/`。
