# 当前导航结构梳理

> 生成日期：2026-07-20
> Batch：1
> 范围：Toolbar 菜单 + Sidebar + Tab 栏 + 弹窗触发

---

## 1. 导航层次

```
┌─────────────────────────────────────────────────────────┐
│ Toolbar (顶部 48px)                                       │
│  ├─ Logo "AI PLC"                                        │
│  ├─ 菜单: 项目/编辑/工具/AI/视图/帮助                       │
│  └─ AI 模型选择器                                          │
├─────────────────────────────────────────────────────────┤
│ Tab 栏 (32px, 横向滚动)                                   │
│  └─ 已打开的 Tab (默认 welcome)                            │
├──────────┬──────────────────────────────┬───────────────┤
│          │                              │                │
│ Sidebar  │       Main Workspace         │ ContextPanel  │
│ (260px)  │       (Tab 内容)              │ (320px)        │
│          │                              │                │
│ 5 Section│                              │ 4 PanelSection │
│ - 工程    │                              │ - 当前工程      │
│ - 对话    │                              │ - 程序块        │
│ - 知识库  │                              │ - 常用变量      │
│ - AI工具  │                              │ - 工程搜索      │
│ - 设置    │                              │                │
│          │                              │                │
├──────────┴──────────────────────────────┴───────────────┤
│ LogPanel (底部，默认折叠)                                 │
│  └─ Tab: 日志 / AI 调用                                   │
└─────────────────────────────────────────────────────────┘
```

## 2. Toolbar 菜单（6 个菜单，22 个菜单项）

### 2.1 项目菜单
- 新建项目 (Ctrl+N) → `project:new` → openCreateDialog
- 导入工程 → `project:import` → importRef.current?.click()
- ─分隔─
- 项目设置 → `project:settings` → openTab('settings')

### 2.2 编辑菜单（全部 disabled）
- 撤销 (Ctrl+Z) → `edit:undo` (disabled)
- 重做 (Ctrl+Y) → `edit:redo` (disabled)
- ─分隔─
- 剪切 (Ctrl+X) → `edit:cut` (disabled)
- 复制 (Ctrl+C) → `edit:copy` (disabled)
- 粘贴 (Ctrl+V) → `edit:paste` (disabled)

**问题**：编辑菜单全部 disabled，无实际功能，建议移除或实现。

### 2.3 工具菜单
- 梯形图生成 → `tool:ladder` → openTab('ladder')
- 程序解析 → `tool:parse` → openTab('parse')
- IO表生成 → `tool:io-table` → openTab('io-table')
- 变量分析 → `tool:variables` → openTab('variables')
- 故障诊断 → `tool:diagnose` → openTab('diagnose')
- ─分隔─
- 工程搜索 → `tool:search` → openTab('chat')
- 索引当前工程 → `tool:index` → addLog('请使用右侧面板')

### 2.4 AI 菜单
- 新建对话 → `ai:new-chat` → handleNewConversation
- ─分隔─
- 模板库 → `ai:templates` → setShowTemplates(true)
- 知识库管理 → `ai:knowledge` → setShowSidebar(true)

### 2.5 视图菜单
- 切换侧栏 (Ctrl+B) → `view:sidebar` → setShowSidebar(v => !v)
- 切换右面板 (Ctrl+J) → `view:context` → setShowContext(v => !v)
- 切换底部面板 (Ctrl+`) → `view:bottom` → setShowBottom(v => !v)

### 2.6 帮助菜单
- 编排管理教程 → `help:orchestrator-tutorial` → openTab('orchestrator') + setShowOrchTutorial(true)
- 关于 AI PLC Assistant → `help:about` → setShowAbout(true)
- API 文档 → `help:api-docs` → window.open('http://127.0.0.1:8005/docs', '_blank')

## 3. Sidebar（5 个 Section）

### 3.1 工程 Section（默认展开）
- 项目列表（listProjects(20)）
  - 点击 → onOpenTab('project', p) → setCurrentProject
- 新建项目按钮 → onCreateProject

### 3.2 对话 Section（默认展开）
- 对话列表（conversations，由 useConversation 提供）
  - 点击 → onSwitchConversation(c.id)
  - 删除按钮 → 二次确认（确认/取消）
- 新建对话按钮 → onNewConversation

### 3.3 知识库 Section（默认折叠）
- 提示词模板 → onOpenTab('templates') → setShowTemplates(true)
- SCL代码模板 → onOpenCodeTemplates()
- 梯形图模板 → onOpenLadderTemplates()
- 导入文档按钮 → fileRef.current?.click() → uploadDocument
- DocGroup 分组（按文件名数字前缀）
  - 基础参考 (1-3)
  - 进阶参考 (4-10)
  - 行业模板 (11-99)

### 3.4 AI 工具 Section（默认展开）
- 7 个工具项：
  - 梯形图生成 → openTab('ladder')
  - 程序解析 → openTab('parse')
  - 故障诊断 → openTab('diagnose')
  - IO表生成 → openTab('io-table')
  - 变量分析 → openTab('variables')
  - 编排管理 → openTab('orchestrator')
  - 机器人 → openTab('robot')

### 3.5 设置 Section
- 模型配置 → openTab('settings')

## 4. Tab 栏

### 4.1 Tab 行为
- 默认 Tab：`welcome`（不可关闭）
- 其他 Tab 可关闭（X 按钮）
- 切换：点击 Tab 头部
- 关闭后：回到最后一个 Tab，若空则回 welcome

### 4.2 Tab 标签
见 `current-pages.md` 第 6 节。

## 5. ContextPanel（4 个 PanelSection，右侧固定）

### 5.1 当前工程（默认展开）
- 项目名 / PLC / TIA / 语言

### 5.2 程序块（默认展开）
- 提示"使用左侧工程搜索查找程序块"或"请先选择项目"

### 5.3 常用变量（默认展开）
- 提示"使用工程搜索查找变量"或"请先选择项目"

### 5.4 工程搜索（默认展开）
- 搜索框 + 搜索按钮
- 结果列表（name/type/content 前 80 字符）

## 6. LogPanel（底部，默认折叠）

### 6.1 Tab: 日志
- 时间 + 级别（INFO/WARN/ERROR） + 消息
- 自动滚动到底

### 6.2 Tab: AI 调用
- 显示"待接入（将显示模型/Token/延迟/回退信息）"

## 7. 弹窗触发关系

| 弹窗 | 触发位置 | 状态变量 |
|------|---------|---------|
| CreateProjectDialog | Toolbar 项目菜单/新建 + Sidebar 工程/新建项目 + Dashboard/新建项目 | showCreateDialog |
| PromptTemplateModal | Toolbar AI 菜单/模板库 + Sidebar 知识库/提示词模板 + Dashboard/常用模板 | showTemplates |
| CodeTemplateModal | Sidebar 知识库/SCL代码模板 | showCodeTemplate |
| LadderTemplateModal | Sidebar 知识库/梯形图模板 | showLadderTemplate |
| About | Toolbar 帮助菜单/关于 | showAbout |
| OrchestratorTutorial | Toolbar 帮助菜单/编排管理教程 + OrchestratorPanel/教程按钮 | showOrchTutorial + localTutorial |

## 8. 导航重复点

| 功能 | Toolbar 菜单 | Sidebar | Dashboard |
|------|-------------|---------|-----------|
| 新建项目 | 项目/新建项目 | 工程/新建项目 | Quick Action 间接（onCreateProject） |
| 梯形图生成 | 工具/梯形图生成 | AI工具/梯形图生成 | Quick Action |
| 程序解析 | 工具/程序解析 | AI工具/程序解析 | Quick Action |
| IO表生成 | 工具/IO表生成 | AI工具/IO表生成 | Quick Action |
| 故障诊断 | 工具/故障诊断 | AI工具/故障诊断 | Quick Action |
| 新建对话 | AI/新建对话 | 对话/新建对话 | — |
| 模板库 | AI/模板库 | 知识库/提示词模板 | 常用模板 |
| 项目设置 | 项目/项目设置 | 设置/模型配置 | — |
| 编排管理 | — | AI工具/编排管理 | — |
| 机器人 | — | AI工具/机器人 | — |
| 变量分析 | 工具/变量分析 | AI工具/变量分析 | — |
| 索引当前工程 | 工具/索引当前工程 | — | — |
| 工程搜索 | 工具/工程搜索 | — | — |
| 切换侧栏 | 视图/切换侧栏 | — | — |
| 切换右面板 | 视图/切换右面板 | — | — |
| 切换底部面板 | 视图/切换底部面板 | — | — |
| 关于 | 帮助/关于 | — | — |
| API 文档 | 帮助/API 文档 | — | — |
| 编排管理教程 | 帮助/编排管理教程 | — | — |

**重复严重的功能**：
- 新建项目（3 处）
- 梯形图生成 / 程序解析 / IO表生成 / 故障诊断（3 处）
- 新建对话（2 处）
- 模板库（3 处）
- 项目设置 / 模型配置（2 处，但指向同一 tab）

## 9. 与主计划 Batch 4 目标对比

主计划 Batch 4 要求左侧导航重组为 4 分组：

```
项目
├── 当前工程
├── 最近工程
├── 新建工程
└── 导入工程

工作区
├── 总览
├── AI 助手
├── 梯形图
├── IO 表
├── 程序解析
├── 变量分析
└── 故障诊断

资源
├── 对话
├── LAD 模板
├── SCL 模板
├── 提示词模板
└── 知识库

系统
├── 编排管理
├── 机器人
├── 日志
└── 设置
```

**当前 vs 目标差异**：
- "项目" 分组：当前是"工程" Section，仅项目列表 + 新建按钮，缺"当前工程"高亮和"导入工程"按钮
- "工作区" 分组：当前无此分组，AI 助手在对话 Section，其他在 AI工具 Section
- "资源" 分组：当前无此分组，对话在独立 Section，模板在知识库 Section
- "系统" 分组：当前无此分组，编排/机器人在 AI工具 Section，日志在底部面板，设置在独立 Section
- **顶部菜单与左侧导航重复**：主计划要求"去除顶部菜单、左侧导航、首页卡片之间的明显重复"

## 10. 键盘快捷键

| 快捷键 | 功能 | 实现状态 |
|--------|------|---------|
| Ctrl+N | 新建项目 | 标注但未实现 keydown 监听 |
| Ctrl+Z | 撤销 | disabled |
| Ctrl+Y | 重做 | disabled |
| Ctrl+X | 剪切 | disabled |
| Ctrl+C | 复制 | disabled |
| Ctrl+V | 粘贴 | disabled |
| Ctrl+B | 切换侧栏 | 标注但未实现 |
| Ctrl+J | 切换右面板 | 标注但未实现 |
| Ctrl+` | 切换底部面板 | 标注但未实现 |
| Enter | 提交（CreateProjectDialog） | 已实现 |
| Esc | 取消（CreateProjectDialog） | 已实现 |
| Enter | 发送消息（ChatArea，非 Shift） | 已实现 |
| Shift+Enter | 换行（ChatArea） | 已实现 |

**问题**：8 个 Ctrl+ 快捷键仅标注但未实现全局 keydown 监听。Batch 4 应实现或移除标注。

## 11. 导航改进建议

### 11.1 Batch 4 改造
1. 重组 Sidebar 为 4 分组（项目/工作区/资源/系统）
2. 移除 Toolbar 6 菜单中与 Sidebar 重复的项
3. 保留 Toolbar 为：Logo + 项目状态 + PLC/TIA/PLCSIM 状态 + 安全模式 + AI 模型
4. 实现 Ctrl+B/J/` 快捷键
5. 移除 disabled 的编辑菜单或实现剪切/复制/粘贴

### 11.2 Batch 5 改造
1. Dashboard 改为工程工作台总览，移除 Quick Action 卡片（已在 Sidebar 覆盖）
2. 添加"继续工作""工作流程""最近活动"区块

### 11.3 Batch 8 改造
1. 弹窗触发统一收纳到 Toolbar 帮助菜单 + Sidebar 资源分组
2. About 弹窗抽离为独立组件
