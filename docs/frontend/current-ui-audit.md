# 当前前端 UI 审核报告

> 生成日期：2026-07-20
> Batch：1
> 范围：`ai-plc-assistant/frontend/`
> 目的：完整审核当前前端，作为重构基线。不进行大规模重构。

---

## 1. 总体结论

当前前端已实现 VS Code 风格深色 IDE 工作台骨架，但**离工业自动化工作台仍有明显差距**：
- 应用外壳仍以单文件 `App.jsx` 承载，未拆分为可维护的布局组件
- 顶部状态栏仅显示 AI 模型，未显示 PLC/TIA/PLCSIM/项目等工业状态
- 左侧导航分 5 个 Section（工程/对话/知识库/AI工具/设置），与顶部菜单存在重复
- 右侧 Inspector 仅显示当前工程 + 工程搜索，未按页面上下文变化
- 底部面板仅 日志/AI调用 两个 Tab，未扩展为 工业工作台所需的 6-7 个 Tab
- 弹窗状态散落在 App.jsx，6 个弹窗独立 useState
- 设置页 Token 输入框 `type="password"`，但测试连接按钮可能将 reply 暴露在 UI
- 无明确的安全等级（Level 0-3）与高风险操作确认
- 测试覆盖仅 1 个组件（LadderGenerator），远低于 80% 目标

## 2. 现有资产（可直接复用）

| 资产 | 位置 | 价值 |
|------|------|------|
| Tailwind ide/accent/text/status 色板 | `tailwind.config.js` | VS Code 风格语义色，已是工业方向 |
| ErrorBoundary | `src/components/ErrorBoundary.jsx` | 全局错误兜底，无需重写 |
| useTabs / useLogs / useModels / useProjects / useConversation / useWorkbenchHistory | `src/hooks/` | 业务 hooks 已抽离，可在 Batch 4 复用 |
| LadderVisualizer V2 | `src/components/LadderVisualizer.jsx` | 结构化 LadderModel 渲染，符合 ASCII-LAD-V2 方向 |
| useWorkbenchHistory + localStorage | `src/hooks/useWorkbenchHistory.js` | 工作台历史持久化，4 个工具页已接入 |
| OrchestratorPanel 中文映射 + 工作流编辑器 | `src/components/OrchestratorPanel.jsx` | 编排管理已完整实现，包含动态工作流 CRUD |
| RobotPanel SVG 可视化 + 急停 + 模拟模式 | `src/components/RobotPanel.jsx` | 机器人模拟已实现，急停有效，但缺真实/仿真/只读模式区分 |

## 3. 现有问题（需在后续 Batch 修复）

### 3.1 应用外壳层

- **App.jsx 187 行单文件**：Toolbar + Tabs + Sidebar + Workspace + ContextPanel + LogPanel + 5 Modal 全在一个文件
- **6 个 Modal 状态散落**：showTemplates / showCodeTemplate / showLadderTemplate / showCreateDialog / showAbout / showOrchTutorial
- **About 弹窗直接内联 JSX**：未抽离为组件
- **Tab 渲染用 `display:none` 保持挂载**：性能可接受，但代码可读性差

### 3.2 顶部状态区

- **Toolbar 仅显示 Logo + 6 菜单 + AI 模型选择器**：缺少项目/后端/PLC/TIA/PLCSIM/安全模式状态
- **菜单与左侧导航重复**：项目/工具/AI/视图 在两处都出现
- **AI 模型选择器圆点 + 文字**：符合"状态必须包含文字"要求，但只反映 enabled，不反映可用性/延迟

### 3.3 左侧导航

- **5 Section 重复顶部菜单**：工程/对话/知识库/AI工具/设置
- **缺少"工作区"分组**：未按主计划 Batch 4 重组为 项目/工作区/资源/系统
- **知识库 DocGroup 按文件名前缀数字分组**（1-3/4-10/11-99）：硬编码分组规则，不灵活
- **删除对话二次确认**：UI 内联确认按钮，符合工业风格，可保留

### 3.4 右侧 Inspector

- **ContextPanel 固定 4 个 Section**：当前工程/程序块/常用变量/工程搜索
- **不随当前 Tab 变化**：主计划 Batch 4 要求 Inspector 根据页面变化（梯形图显示变量/网络/模板，IO 表显示地址范围/分类/校验等）
- **工程搜索有效但简化**：仅展示 name + type + content 前 80 字符

### 3.5 底部面板

- **LogPanel 仅 日志/AI调用 两 Tab**：AI 调用 Tab 显示"待接入"
- **未扩展为 6 Tab**：日志/AI调用/任务/PLC通信/TIA Openness/问题/错误
- **默认折叠**：折叠后只显示 Tab 头，符合工业风格

### 3.6 首页（Dashboard）

- **欢迎语 + 4 个快捷操作卡片**：类似 SaaS 后台首页，不是工业工作台总览
- **缺少全局状态区**：仅一个"系统状态"卡片（依赖 orchestratorHealth），缺 PLC/TIA/PLCSIM/MCP/安全模式
- **继续工作 / 工作流程 / 最近活动 区块未实现**
- **无虚构统计图**：当前未伪造，符合要求

### 3.7 AI 助手（ChatArea）

- **消息类型支持不全**：仅 user/assistant + type='ladder'，未统一支持 Markdown/代码/变量表/IO表/ASCII-LAD/任务进度/工具调用/文件/警告/错误/导出结果/引用来源
- **输入区极简**：仅一个 input + 发送按钮，缺当前项目/当前模型/模板/附件/引用工程/停止生成
- **SSE 状态显示不全**：仅 streaming 标志，未显示当前模型/停止按钮/已生成内容字数
- **LadderResult 默认 SVG 模式**：与主计划 Batch 6 要求"ASCII-LAD 默认显示"不一致

### 3.8 PLC 工具页面（5 个）

| 页面 | 输入 | 输出 | 状态 | 问题 |
|------|------|------|------|------|
| 梯形图生成 LadderGenerator | textarea | 标题/变量表/网络/源码/导出 | loading/pipelineLoading | 已接入 runNlToSim 全链路，有历史记录，SVG/源码切换默认 SVG |
| 程序解析 CodeExplainer | textarea + 语言选择 | ReactMarkdown 流式 | loading | 双栏布局，无文件上传，无风险检查 |
| IO 表生成 IoTableGenerator | textarea 设备描述 | ReactMarkdown 表格 | loading | 双栏布局，无地址冲突检查，无 CSV 导出（仅复制） |
| 变量分析 VariableAnalyzer | textarea 代码 | ReactMarkdown 表格 | loading | 双栏布局，无地址冲突/未使用变量分析 |
| 故障诊断 FaultDiagnosis | textarea + PLC型号 + 错误代码 | ReactMarkdown | loading | 双栏布局，无 PLC 状态/IO 状态/排查步骤结构化 |

**共性问题**：
- 5 个页面交互流程不统一（梯形图单栏 + 历史，其他 4 个双栏）
- 状态机不完整（仅 loading，无 校验失败/执行成功/执行失败/部分成功/无结果/后端离线/模型不可用）
- IO表/变量分析 复用同样的"代码输入 + AI 流式输出"模式，可抽象
- 4 个 AI 流式页面均硬编码 `model_id: 'deepseek'`，未用 useModels 的 selectedModel

### 3.9 编排管理 OrchestratorPanel

- **已完整实现**：3 状态卡片 + 工作流列表（内置/自定义）+ 工具列表（搜索/分组）+ 工作流编辑器 + 执行结果 + 教程弹窗
- **未伪造在线状态**：servers_connected 数量来自后端，符合要求
- **工具搜索有效**：中英文均可搜
- **工作流编辑器完整**：步骤增删/上下移/参数 JSON 编辑/保存/执行测试
- **教程弹窗内容详尽**：6 章节，含示例与安全说明
- **问题**：编辑器 GripVertical 显示可拖拽光标但未实现拖拽；保存的工作流未做参数 schema 校验

### 3.10 机器人 RobotPanel

- **SVG 可视化精致**：传送带 + 机械臂 + 夹爪 + 物料动画 + 急停指示灯
- **急停按钮有效**：触发后所有控制禁用，状态重置
- **手动控制完整**：回位/拾取/放置/自动循环 + 传送带 + 单轴
- **自动循环调用编排层工作流**：`robot_pick_place`，失败降级本地模拟
- **关键缺陷**：未区分演示/仿真/只读/真实控制模式，无真实控制安全提示
- **模拟急停日志明确"不控制真实设备"**：符合安全要求

### 3.11 设置 SettingsPanel

- **5 个 Provider 卡片**：DeepSeek/OpenAI/Kimi/Claude/Custom，每个有 API Key + Base URL + Model + 测试连接
- **API Key 输入 type="password"**：符合"默认隐藏"
- **测试连接结果展示 reply 字段**：可能泄露 Token 关联的模型回复，但只是 UI 展示，未写入文件
- **PLC 默认配置**：PLC型号/TIA版本/编程语言
- **缺少分类**：未按主计划 Batch 8 拆为 模型/后端/项目/知识库/界面/安全/高级
- **Token 不出现在截图**：未验证；需在 Batch 8 加 `data-testid` + 截图排除
- **测试连接前自动保存 form**：`handleTest` 先调用 updateSettings(form) 再 testProvider，避免测试旧配置

### 3.12 弹窗

| 弹窗 | 触发 | 实现 | 问题 |
|------|------|------|------|
| PromptTemplateModal | 菜单 AI/模板库 + Sidebar 提示词模板 + Dashboard 常用模板 | 分类侧栏 + 模板列表 + 变量填写 + 内容预览 | 使用 `bg-surface` 类名，但 tailwind.config 未定义 `surface`，依赖继承的深色背景 |
| CodeTemplateModal | Sidebar SCL代码模板 | SCL/文档切换 + 模板列表 + 代码展示 + IO 表 | 同上 `bg-surface` 问题 |
| LadderTemplateModal | Sidebar 梯形图模板 | 模板列表 + ASCII-LAD 文本展示 | 同上 `bg-surface` 问题 |
| CreateProjectDialog | 菜单 项目/新建 + Dashboard 新建项目 + Sidebar 新建项目 | 名称 + PLC型号 + TIA版本 + 编程语言 | 完整，支持 Esc 取消 |
| About | 菜单 帮助/关于 | 内联在 App.jsx | 未抽组件，样式与其他弹窗不一致 |
| OrchestratorTutorial | 菜单 帮助/编排管理教程 + OrchestratorPanel 教程按钮 | 6 章节教程弹窗 | 在 OrchestratorPanel 内部，复用性好 |

**共性问题**：
- 3 个 Template Modal 使用 `bg-surface` 类名但 tailwind.config 未定义，可能是历史遗留
- 弹窗不支持焦点锁定（focus trap）
- 弹窗不支持 Esc 关闭（仅 CreateProjectDialog 支持）
- 危险按钮文案不具体（如"删除"而非"确认删除对话"）

### 3.13 Web 兼容性

- **API_BASE 硬编码生产地址**：`http://127.0.0.1:8005/api`，无法环境变量覆盖
- **window.open API 文档**：`http://127.0.0.1:8005/docs`，Web 部署后失效
- **CSP 限制 connect-src**：`'self' http://localhost:*`，Web 部署需调整
- **Electron 专属调用极少**：仅 preload.js 暴露 `electronAPI.getAppVersion()`，业务代码未使用，Web 兼容性好
- **文件上传/下载全用 Blob + FormData**：浏览器原生 API，Web 兼容
- **SSE 用 fetch + ReadableStream**：浏览器原生，Web 兼容
- **localStorage 历史记录**：浏览器原生，Web 兼容
- **无 `window.electronAPI` 业务判断散落**：Batch 2 改造简单

### 3.14 测试覆盖

| 范围 | 现状 | 目标 |
|------|------|------|
| 单元测试 | 1 个组件（LadderGenerator）2 个测试 | 80% 覆盖 |
| 集成测试 | 0 | 项目切换/对话切换/页面切换/SSE/上传/导出 |
| E2E 测试 | 0 | 启动/新建对话/发送消息/打开工具页/折叠面板 |
| 视觉回归 | 0 | 14 页面 x 2 尺寸 before/after 对比 |

## 4. 验收基线

| 指标 | 结果 |
|------|------|
| `npm install` | 成功（node_modules 就绪） |
| `npm run test` | 1 file, 2 tests passed, 0 failed |
| `npm run build` | 1967 modules, dist/index.html 0.61KB, CSS 20.87KB, JS 424.97KB (gzip 124.72KB) |
| Electron 启动 | 待 Batch 2 验证 |
| 主要页面截图 | 见 `screenshots/before/`（Batch 1 末尾生成） |

## 5. 与主计划差距清单

| 主计划要求 | 现状 | 待做 Batch |
|------|------|------|
| API 地址环境化 | 硬编码 | Batch 2 |
| dev:web/build:web/preview:web 脚本 | 缺 | Batch 2 |
| src/platform/runtime.js | 缺 | Batch 2 |
| src/styles/tokens.css/base.css/components.css/utilities.css | 缺 | Batch 3 |
| 基础组件（Button/StatusBadge/Panel/Tabs 等 20 个） | 缺 | Batch 3 |
| src/layout/ AppShell 拆分 | App.jsx 单文件 | Batch 4 |
| 顶部 GlobalStatusBar | 仅 Toolbar 显示模型 | Batch 4 |
| 左侧导航 4 分组（项目/工作区/资源/系统） | 5 Section 重复菜单 | Batch 4 |
| Inspector 按页面变化 | 固定 4 Section | Batch 4 |
| 底部 6 Tab | 2 Tab | Batch 4 |
| 首页工程工作台总览 | SaaS 风格欢迎页 | Batch 5 |
| AI 助手消息类型统一 + 输入区组件化 | 单 input | Batch 6 |
| ASCII-LAD 默认显示 | SVG 默认 | Batch 6 |
| 5 个 PLC 工具页面统一交互 | 各自实现 | Batch 7 |
| 安全等级 0-3 + 高风险确认 | 缺 | Batch 8 |
| 弹窗焦点锁定 + Esc + 具体危险文案 | 部分支持 | Batch 8 |
| Token 不出现在截图 | 未验证 | Batch 8 |
| 响应式 1366/1600/1920/2560 | 未测试 | Batch 9 |
| 可访问性 aria-label/对比度/焦点 | 部分 | Batch 9 |
| 单元/集成/E2E 测试 | 1/0/0 | Batch 9 |
| 截图回归 | 0 | Batch 9 |

---

## 6. 建议

按主计划 Batch 顺序执行：
1. **Batch 2 优先**：API 环境化 + dev:web/build:web 脚本 + platform/runtime.js，建立 Web/Electron 双模式基础
2. **Batch 3 设计系统**：保留 Tailwind ide.* 色板，在 tokens.css 中定义为 CSS 变量，tailwind.config.js 引用变量
3. **Batch 4 应用外壳**：拆 App.jsx 为 9 个 layout 组件，按主计划重组导航
4. **Batch 5-8 业务页**：基于设计系统 + 外壳逐步重构
5. **Batch 9 收尾**：Playwright E2E + 视觉回归 + 性能优化
