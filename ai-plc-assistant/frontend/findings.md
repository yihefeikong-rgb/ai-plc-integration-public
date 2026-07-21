# 前端重构研究发现 — AI PLC Assistant Frontend

> 起始日期：2026-07-20
> 原则：记录审核中发现的现有问题、风险、兼容性障碍。区分原有问题与新增问题。

## 2026-07-20：收尾批次修复（F-015/F-017/F-018/F-038/F-039/F-040/F-041）

| 编号 | 状态 | 修复内容 |
|------|------|---------|
| F-015 | ✅ 已修复 | 新增 useFocusTrap hook，应用到 5 个弹窗（ConfirmDialog + 3 TemplateModal + CreateProjectDialog） |
| F-017 | ✅ 已修复 | ConfirmDialog 新增 dangerAction prop 自动取 DANGER_BUTTON_LABELS；PrimarySidebar 删除对话按钮文案改"确认删除对话" |
| F-018 | ✅ 已修复 | GlobalStatusBar 安全模式项接入 safetyLevels 4 等级，支持点击切换 + localStorage 持久化 |
| F-038 | ✅ 已修复 | ChatArea.jsx:134 调用改为 networks={[n]}，LadderVisualizer 已有 fallback 显示 ASCII code |
| F-039 | ✅ 已修复 | useConversation onError 保留 streamContentRef.current + 追加错误提示，非流式 fallback 失败也保留 |
| F-040 | ✅ 已修复 | useConversation 新增 msgIdRef，所有消息加 id；ChatArea key 用 msg.id；LadderResult 内 key 用 v.address/n.number |
| F-041 | ✅ 已修复 | MessageBlock 新增 CODE 分支，CodeMessage 组件用 ui/CodeViewer 渲染 |

### 仍待修复
- F-019 机器人 4 模式（演示/仿真/只读/真实控制）
- F-037 useTabs closeTab updater 内副作用反模式（需合并 tabs+activeTab 为单一 state）
- ToolStatusBar 接入 5 个工具页面 + 状态机完整改造
- 附件上传按钮 onClick
- layout/ 单元测试
- 响应式 4 尺寸截图回归 / E2E 测试 / Lighthouse 性能测试
- CSP 收紧 connect-src https: 到具体域名
- Batch 8/9 独立复审

---

---

## F-001：API_BASE 硬编码生产地址

- **位置**：`ai-plc-assistant/frontend/src/api.js:4`
- **现象**：
  ```js
  export const API_BASE = import.meta.env.DEV ? '/api' : 'http://127.0.0.1:8005/api'
  ```
  生产模式硬编码 `http://127.0.0.1:8005`，无法通过环境变量覆盖。
- **影响**：Web 部署到非本机后端时无法配置地址；Electron 模式正常。
- **分类**：原有问题。Batch 2 修复。

## F-002：脚本命名不区分 web/electron

- **位置**：`ai-plc-assistant/frontend/package.json:8-16`
- **现象**：仅有 `dev:renderer`/`dev:electron`/`dev`/`build`/`pack`/`dist`/`preview`，缺少 `dev:web`/`build:web`/`preview:web`/`build:electron` 显式命名。
- **影响**：双模式边界不清晰，主计划 Batch 2 要求明确区分。
- **分类**：原有问题。Batch 2 修复。

## F-003：App.jsx 单文件承载布局+路由+弹窗

- **位置**：`ai-plc-assistant/frontend/src/App.jsx`
- **现象**：187 行单文件包含 Toolbar/Sidebar/Tabs/Workspace/LogPanel/Modal 等所有布局，并直接管理 6 个弹窗状态。
- **影响**：Batch 4 应用外壳拆分难度增大；状态散落，难以维护。
- **分类**：原有问题。Batch 4 修复。

## F-004：测试覆盖极低

- **位置**：`ai-plc-assistant/frontend/src/components/`
- **现象**：仅 `LadderGenerator.test.jsx` 一个测试文件，2 个测试。
- **影响**：主计划 Batch 9 要求单元/集成/E2E 三级覆盖；当前远低于 80%。
- **分类**：原有问题。Batch 9 修复。

## F-005：Tailwind 配色与 ide 语义已部分就绪

- **位置**：`ai-plc-assistant/frontend/tailwind.config.js`
- **现象**：已定义 `ide.*`、`accent.*`、`text.*`、`status.*` 四组语义色，VS Code 风格深色主题。
- **影响**：Batch 3 设计系统改造可基于现有 tokens 扩展，不需要推倒重来。
- **分类**：原有资产。Batch 3 利用。

## F-006：OrchestratorPanel 单文件 871 行

- **位置**：`ai-plc-assistant/frontend/src/components/OrchestratorPanel.jsx`
- **现象**：871 行单文件，包含主组件 + 6 个子组件（StatCard/StepResultRow/ToolGroup/RunDialog/TutorialModal/Section/ToolCard/Step）+ 中文映射表 + 工作流编辑器。
- **影响**：超过 800 行阈值，可维护性差。
- **分类**：原有问题。Batch 7/8 拆分。

## F-007：5 个 AI 工具页硬编码 model_id='deepseek'

- **位置**：
  - `LadderGenerator.jsx:46` `generateLadder(description, {}, '', 'deepseek')`（位置参数第 4 位）
  - `CodeExplainer.jsx:57` `model_id: 'deepseek'`
  - `IoTableGenerator.jsx:52` `model_id: 'deepseek'`
  - `FaultDiagnosis.jsx:59` `model_id: 'deepseek'`
  - `VariableAnalyzer.jsx:49` `model_id: 'deepseek'`
- **现象**：5 个 AI 工具页面未用 useModels 的 selectedModel，硬编码 'deepseek'。LadderGenerator 用 `generateLadder()` 位置参数，其余 4 个用 `streamChat({ model_id })` 命名参数。
- **影响**：Toolbar 切换模型后，5 个工具页仍用 deepseek，行为不一致。
- **分类**：原有问题。Batch 7 已修复（5 个页面加 selectedModel prop + MainWorkspace 透传）。

## F-008：5 个 PLC 工具页面交互不统一

- **位置**：LadderGenerator/CodeExplainer/FaultDiagnosis/IoTableGenerator/VariableAnalyzer
- **现象**：
  - LadderGenerator 单栏 + 历史记录 + 双按钮（生成/仿真）
  - 其他 4 个双栏 + 历史记录 + 单按钮
- **影响**：用户认知负担大，主计划 Batch 7 要求统一交互流程。
- **分类**：原有问题。Batch 7 修复。

## F-009：PLC 工具页面状态机不完整

- **位置**：5 个工具页
- **现象**：仅 loading 状态，缺 校验失败/执行成功/执行失败/部分成功/无结果/后端离线/模型不可用。
- **影响**：错误状态展示不清晰，用户无法判断后续操作。
- **分类**：原有问题。Batch 7 修复。

## F-010：ContextPanel 不随当前 Tab 变化

- **位置**：`ai-plc-assistant/frontend/src/components/ContextPanel.jsx`
- **现象**：固定 4 个 PanelSection（当前工程/程序块/常用变量/工程搜索）。
- **影响**：主计划 Batch 4 要求 Inspector 根据页面变化（梯形图显示变量/网络/模板，IO 表显示地址范围/分类/校验等）。
- **分类**：原有问题。Batch 4 修复。

## F-011：底部面板仅 2 Tab

- **位置**：`ai-plc-assistant/frontend/src/components/LogPanel.jsx:4-7`
- **现象**：仅 日志/AI调用 两 Tab，AI 调用 Tab 显示"待接入"。
- **影响**：主计划 Batch 4 要求扩展为 6 Tab（日志/AI调用/任务/PLC通信/TIA Openness/问题/错误）。
- **分类**：原有问题。Batch 4 修复。

## F-012：3 个 Template Modal 使用未定义的 bg-surface 类名

- **位置**：
  - `PromptTemplateModal.jsx:48` `bg-surface w-[700px]`
  - `CodeTemplateModal.jsx:51` `bg-surface w-[800px]`
  - `LadderTemplateModal.jsx:33` `bg-surface w-[850px]`
- **现象**：使用 `bg-surface` / `border-surface-border` / `bg-surface-alt` / `bg-surface-hover`，但 `tailwind.config.js` 未定义 `surface` 色板。
- **影响**：弹窗背景色依赖继承的深色背景，可能在某些场景显示异常。
- **分类**：原有问题。Batch 3 修复（添加 surface 色板或迁移到 ide.*）。

## F-013：8 个 Ctrl 快捷键未实现

- **位置**：`ai-plc-assistant/frontend/src/components/Toolbar.jsx:52-110`
- **现象**：菜单项标注 Ctrl+N/Z/Y/X/C/V/B/J/` 快捷键，但无全局 keydown 监听实现。
- **影响**：用户期望快捷键可用，实际无效。
- **分类**：原有问题。Batch 4 实现 or 移除标注。

## F-014：编辑菜单全部 disabled 无实际功能

- **位置**：`Toolbar.jsx:62-72`
- **现象**：编辑菜单 5 项（撤销/重做/剪切/复制/粘贴）全部 disabled。
- **影响**：菜单占用空间但无功能。
- **分类**：原有问题。Batch 4 移除 or 实现。

## F-015：弹窗无焦点锁定（focus trap）

- **位置**：6 个弹窗
- **现象**：弹窗打开后 Tab 键可跳到弹窗外元素，不符合可访问性要求。
- **影响**：可访问性差，主计划 Batch 8 要求焦点锁定。
- **分类**：原有问题。Batch 8 修复。

## F-016：仅 CreateProjectDialog 支持 Esc 关闭

- **位置**：6 个弹窗中仅 `CreateProjectDialog.jsx:31` 监听 Escape
- **现象**：其他 5 个弹窗不支持 Esc 关闭。
- **影响**：可访问性不一致。
- **分类**：原有问题。Batch 8 修复。

## F-017：危险按钮文案不具体

- **位置**：Sidebar 删除对话按钮等
- **现象**：删除确认按钮显示"确认"，主计划要求"确认删除对话"等具体文案。
- **影响**：用户可能误操作。
- **分类**：原有问题。Batch 8 修复。

## F-018：安全等级 0-3 未实现

- **位置**：无
- **现象**：主计划 Batch 8 要求 Level 0 只读 / Level 1 本地写入 / Level 2 工程修改 / Level 3 设备控制，高风险操作确认显示 PLC/IP/型号/项目/状态/影响/可回滚/风险说明。
- **影响**：安全边界不清晰，工业场景风险大。
- **分类**：原有缺失。Batch 8 实现。

## F-019：机器人未区分演示/仿真/只读/真实控制模式

- **位置**：`ai-plc-assistant/frontend/src/components/RobotPanel.jsx`
- **现象**：仅模拟模式，无模式切换，无真实控制安全提示。
- **影响**：主计划 Batch 8 要求明确区分 4 种模式，真实控制必须有安全提示。
- **分类**：原有缺失。Batch 8 实现。

## F-020：OrchestratorPanel/RobotPanel 直接 fetch 未复用 api.js

- **位置**：
  - `OrchestratorPanel.jsx:101-117` apiGet/apiPost/apiDelete
  - `RobotPanel.jsx:132` 直接 fetch
- **现象**：未用 api.js 的 request 函数，重复封装请求逻辑。
- **影响**：维护成本高，本地 Token header 处理不一致（OrchestratorPanel 已用 localControlHeaders，RobotPanel 自行展开 LOCAL_API_TOKEN）。
- **分类**：原有问题。后续 Batch 修复。

## F-021：window.open 硬编码 API 文档 URL

- **位置**：`ai-plc-assistant/frontend/src/App.jsx:82`
- **现象**：`window.open('http://127.0.0.1:8005/docs', '_blank')`
- **影响**：Web 部署后失效。
- **分类**：原有问题。Batch 2 修复。

## F-022：CSP 限制 connect-src 到 localhost

- **位置**：`ai-plc-assistant/frontend/index.html:6`
- **现象**：`connect-src 'self' http://localhost:*`
- **影响**：Web 部署后调用远程 API 被拦截。
- **分类**：原有问题。Batch 2 修复。

## F-023：API Key 返回未脱敏

- **位置**：后端 `/settings` 接口
- **现象**：getSettings() 返回完整 API Key，前端可读。
- **影响**：API Key 出现在网络响应中，可能被截获。
- **分类**：原有问题（后端）。前端不修改，记录到 findings.md。

## F-024：测试连接 reply 字段可能泄露敏感信息

- **位置**：`SettingsPanel.jsx:69` `testResult.reply`
- **现象**：测试连接结果 reply 字段是模型回复，展示在 UI。
- **影响**：reply 可能包含敏感信息，出现在截图。
- **分类**：原有问题。Batch 8 修复（仅 dev 模式展示或脱敏）。

## F-025：Tab 路由用内部状态，刷新后丢失

- **位置**：`ai-plc-assistant/frontend/src/hooks/useTabs.js`
- **现象**：无 URL 路由，浏览器刷新后 Tab 状态丢失。
- **影响**：无法分享 URL 定位到特定 Tab，浏览器后退/前进无效。
- **分类**：原有问题。Batch 4 或 9 评估是否需 URL 路由。

## F-026：LadderResult 默认 SVG 模式与主计划要求不一致

- **位置**：`ai-plc-assistant/frontend/src/components/ChatArea.jsx:37`
- **现象**：`const [svgMode, setSvgMode] = useState(true)` 默认 SVG。
- **影响**：主计划 Batch 6 要求"ASCII-LAD 默认显示"。
- **分类**：原有问题。Batch 6 修复。

## F-027：Batch 2 复审 — settings 截图体积差异分析（非回归）

- **位置**：`docs/frontend/screenshots/before/settings-*.png`（基线 60KB/77KB）vs `docs/frontend/screenshots/batch2-verify/settings-*.png`（34KB/38KB）
- **现象**：Batch 2 复审发现 settings 页截图体积缩小 ~45-50%，疑似 UI 回归。
- **调查过程**：
  1. `git diff --stat HEAD -- src/components/ src/hooks/ electron/ backend/` 确认业务代码零改动
  2. 诊断脚本 `scripts/diagnose-settings.mjs`：200ms（loading）与 3000ms（loaded）截图大小几乎一致（34362 vs 34349）
  3. 验证脚本 `scripts/verify-settings-loading.mjs`：用 Playwright route 拦截 API 请求强制保持 loading 状态，截图仍为 34265/38272，与 loaded 状态 34351/38337 几乎一致
- **结论**：**非 UI 回归**。基线图的 60KB/77KB 是 Batch 1 首次 vite preview 启动时的过渡状态（资源首次加载 + CSS/JS 缓存未热）导致的异常值，无法在 warm 状态下复现。Batch 2 未修改任何业务代码，settings 页 UI 行为与基线一致。
- **分类**：基线截图环境异常，非回归。已关闭。

## F-028：vite.config.js 缺少 /docs proxy（Batch 2 复审提出）

- **位置**：`ai-plc-assistant/frontend/vite.config.js`
- **现象**：dev 模式 `API_DOCS_URL` 推导为 `/docs`，但 vite proxy 仅配了 `/api`，导致 dev:web 下点击"API 文档"打开 `http://localhost:5173/docs` 返回 404。
- **影响**：dev 模式 API 文档不可达。
- **分类**：Batch 2 已修复（vite.config.js 补 `/docs` 和 `/openapi.json` proxy）。

## F-029：BottomPanel collapsed 语义 bug — 折叠=卸载（Batch 4 复审）

- **位置**：`ai-plc-assistant/frontend/src/layout/AppShell.jsx:210-218`（修复前）
- **现象**：`collapsed={!showBottom ? true : undefined}` 在 `showBottom=true` 时永远是 `undefined`，`setCollapsed={setShowBottom}` 导致用户点折叠按钮 → `setShowBottom(false)` → 整个 BottomPanel 卸载 → Tab 栏消失，再也无法通过点击展开（只能 Ctrl+\` 恢复）。
- **影响**：UX 严重倒退，折叠按钮一点就永久消失。
- **分类**：Batch 4 迁移引入的回归。已修复（分离 `showBottom` 挂载状态与 `bottomCollapsed` 折叠状态）。

## F-030：菜单"导入工程" onChange 丢失（Batch 4 复审）

- **位置**：`ai-plc-assistant/frontend/src/layout/AppShell.jsx:59, 220-225`（修复前）
- **现象**：`useProjects` 返回 `handleImportProject`，但 `AppShell` 解构时只取 `importRef`，未取 `handleImportProject`；`<input ref={importRef}>` 也未绑定 `onChange`。点击菜单"项目 → 导入工程"会打开文件选择器，但选完文件后无任何反应。
- **影响**：菜单导入功能失效，迁移回归。
- **分类**：Batch 4 迁移遗漏。已修复（补解构 `handleImportProject` + input 加 `onChange={handleImportProject}`）。

## F-031：layoutContextValue 未 memo 化（Batch 4 复审）

- **位置**：`ai-plc-assistant/frontend/src/layout/AppShell.jsx:131-142`（修复前）
- **现象**：`layoutContextValue` 每次渲染新建对象，内联 `registerModal` 函数每次渲染新引用。所有消费 `useLayout()` 的组件会因 context value 引用变化而强制 re-render。
- **影响**：当 Batch 5+ 业务组件接入 `useLayout()` 时，抵消 React.memo 优化，性能下降。
- **分类**：Batch 4 性能隐患。已修复（`registerModal` 用 `useCallback([], [])`，`layoutContextValue` 用 `useMemo`）。

## F-032：键盘 useEffect 依赖数组语义不严谨（Batch 4 复审）

- **位置**：`ai-plc-assistant/frontend/src/layout/AppShell.jsx:121-129`（修复前）
- **现象**：`useEffect` 依赖数组 `[setShowSidebar, setShowContext, setShowBottom]`，但 React 18 `useState` dispatch 是稳定引用，等价于空依赖。当前行为正确，但语义不严谨，易让后来者误以为"setter 变化会重新绑定"。
- **影响**：无实际 bug，但可读性误导，且若未来 `usePersistentState` 实现变化可能引入 stale closure。
- **分类**：Batch 4 代码质量问题。已修复（依赖数组改 `[]` + `eslint-disable-next-line` + 注释说明 setter 引用稳定）。

## F-033：useTabs closeTab stale closure（原有问题，Batch 5 已修复）

- **位置**：`ai-plc-assistant/frontend/src/hooks/useTabs.js:28-38`
- **现象**：`closeTab` 的 `setActiveTab` 函数式更新里引用了闭包变量 `tabs`（渲染时快照），而非使用 `setTabs` 的最新值。连续调用 `closeTab` 两次，第二次的 `tabs` 仍是第一次调用前的值，可能切回已关闭的 tab。
- **影响**：快速连点关闭按钮可能 activeTab 指向已不存在的 tab，导致 MainWorkspace 渲染空白。
- **分类**：原有问题。Batch 5 已修复（在 setTabs updater 内同步 setActiveTab，消除闭包依赖）。
- **残留**：F-037（updater 内副作用反模式）。

## F-034：Dashboard useEffect `if (!conversations)` 死代码（Batch 5 复审）

- **位置**：`ai-plc-assistant/frontend/src/components/Dashboard.jsx:92-100`（修复前）
- **现象**：useEffect 中 `if (!conversations) listConversations(5)...` 条件永远为 false，因为 useConversation 初始值是 `[]`（空数组，truthy）。`recentConversations` state 永远不被调用，是死代码。
- **影响**：可读性陷阱，未来 useConversation 移除 refreshConversations 时 Dashboard 不会自取。
- **分类**：Batch 5 可读性问题。已修复（改 `conversations.length === 0` + 依赖数组 `[conversations]`）。

## F-035：handleConvClick else 分支死代码（Batch 5 复审）

- **位置**：`ai-plc-assistant/frontend/src/components/Dashboard.jsx:112-115`（修复前）
- **现象**：`if (onSwitchConversation) onSwitchConversation(c.id) else onOpenTab?.('chat')` — MainWorkspace 永远传 onSwitchConversation（来自 AppShell 的 handleSwitchConversation），else 分支永远不执行。
- **影响**：死代码，可读性误导。
- **分类**：Batch 5 死代码。已修复（简化为 `onSwitchConversation?.(c.id)`）。

## F-036：AppShell onImportProject 内联函数未 memo（Batch 5 复审）

- **位置**：`ai-plc-assistant/frontend/src/layout/AppShell.jsx:197`（修复前）
- **现象**：`onImportProject={() => importRef.current?.click()}` 内联箭头函数每次渲染新建引用，与 D-FE-013 memo 化精神不一致。
- **影响**：无实际 bug（Dashboard 不把它当 useEffect 依赖），但代码质量不一致。
- **分类**：Batch 5 代码质量。已修复（useCallback 包装为 handleImportProjectClick）。

## F-037：useTabs closeTab updater 内副作用反模式（Batch 5 复审）

- **位置**：`ai-plc-assistant/frontend/src/hooks/useTabs.js:28-38`
- **现象**：F-033 修复方案在 setTabs updater 内调用 setActiveTab，属于"updater 内触发副作用"反模式。React 19 严格模式可能警告，StrictMode 双调用会导致 setActiveTab 被调用两次（幂等但仍是反模式）。
- **影响**：无当前 bug，但未来 React 版本可能告警。
- **分类**：Batch 5 引入的技术债。留 Batch 9 根治（合并 tabs+activeTab 为单一 state object）。

## F-038：LadderVisualizer prop 不匹配（Batch 6 复审，预存在问题）

- **位置**：`ai-plc-assistant/frontend/src/components/ChatArea.jsx:134`（调用方）+ `ai-plc-assistant/frontend/src/components/LadderVisualizer.jsx:143`（定义方）
- **现象**：ChatArea 调用 `<LadderVisualizer code={n.code} networkTitle={...} />`，但 LadderVisualizer 签名为 `function LadderVisualizer({ networks })`，只接受 `networks` 数组。prop 不匹配，图形模式显示"无梯形图数据"。
- **影响**：用户切到图形模式看到空白。F-026 修复后默认 text 模式，降低暴露概率。
- **分类**：预存在问题（Batch 6 之前 svgMode=true 默认就暴露）。留后续 Batch 统一 ladder 数据契约时修复。

## F-039：SSE onError 替换最后一条消息时丢失已生成内容（Batch 6 复审）

- **位置**：`ai-plc-assistant/frontend/src/hooks/useConversation.js:156-165`
- **现象**：onError 回调 `setMessages` 替换最后一条为"调用失败: {err.message}"，丢失了 streaming 已生成的半截内容。
- **影响**：用户看到错误时已 streaming 出来的内容消失，体验差。
- **分类**：Batch 6 UX 问题。留 Batch 9 修复（保留 content + 追加错误提示）。

## F-040：MessageBlock/LadderResult 数组索引 key（Batch 6 复审）

- **位置**：`ai-plc-assistant/frontend/src/components/ChatArea.jsx:424, 90, 118`
- **现象**：`messages.map((msg, i) => <MessageBlock key={i} ...>)` + `variables.map((v, i) => <tr key={i}>...)` + `networks.map((n, i) => <div key={i}>...)`
- **影响**：当前 append-only 语义无 bug，但未来支持消息重试/变量重排时会复用错误 DOM。
- **分类**：Batch 6 代码质量。留 Batch 9 修复（用 stable key 如 msg.id/v.address/n.number）。

## F-041：CODE 消息类型未独立分发（Batch 6 复审）

- **位置**：`ai-plc-assistant/frontend/src/components/ChatArea.jsx:22-36, 251-268`
- **现象**：MSG_TYPES 定义了 `CODE: 'code'`，但 MessageBlock 分发链没有为 code 类型单独处理，会落到 ReactMarkdown 分支。
- **影响**：主计划 §9.2 把 code 与 markdown 分开是为了 code 用独立 CodeViewer 组件渲染（语法高亮）。当前用 ReactMarkdown 渲染 code 类型，未达到主计划意图。
- **分类**：Batch 6 不完整。留后续 Batch 接入 ui/CodeViewer 时增加 code 分发分支。

---

## 2026-07-20：全量复审新发现（F-042 ~ F-090，47 条）

> 由 code-reviewer agent 对 master @ `9c71967` 做的独立全量复审。
> 完整报告：`audit-2026-07-20.md`
> 评分：6.8/10 — CONDITIONAL PASS
> 按 HIGH / MEDIUM / LOW 严重级别分组。F-062 与 F-037 合并看待；F-090 与 F-043 合并。

### HIGH（6 项 — 阻断生产部署）

#### F-050: OrchestratorInspector 硬编码"状态：运行中"伪造后端状态
- **位置**：`src/layout/InspectorPanel.jsx:383-411`
- **现象**：`<KeyValue k="状态" v="运行中" />` 与 `· Team Lead（调度）` 等硬编码字符串，未接 `orchestratorHealth()` 真实状态。
- **影响**：用户看到"运行中"假数据，实际后端可能未启动。`GlobalStatusBar` 已接真实 API，这里却硬编码，自相矛盾。**违反项目"不伪造"安全原则**。
- **分类**：收尾批次 D-3 引入
- **严重级别**：HIGH

#### F-051: IoTableInspector 地址范围与校验全部硬编码假数据
- **位置**：`src/layout/InspectorPanel.jsx:290-308`
- **现象**：永远显示固定的 I0.0~I0.7 / Q0.0~Q0.7 / M0.0~M14.7 范围与"地址冲突检测/重复分配检测/类型匹配校验"等静态文案，与 `currentProject` 和实际 IO 表无关。
- **影响**：用户以为系统已做校验，实际未做。**工业场景下"假校验通过"比"未校验"更危险**。
- **分类**：收尾批次 D-3 引入
- **严重级别**：HIGH

#### F-067: Dashboard 全局状态 4 项硬编码与 GlobalStatusBar 矛盾
- **位置**：`src/components/Dashboard.jsx:128-141`
- **现象**：`<StatusRow label="PLC" value="未连接" tone="offline" />` 等 4 项永远显示固定值，`GlobalStatusBar` 已接 `listServers()`/`healthCheck()`/`orchestratorHealth()` 真实状态。
- **影响**：用户在 Dashboard 与 GlobalStatusBar 看到不一致的 PLC/TIA/PLCSIM 状态，困惑。
- **分类**：Batch 5 重构遗留
- **严重级别**：HIGH

#### F-068: Dashboard 安全模式硬编码"只读"与 GlobalStatusBar localStorage 脱节
- **位置**：`src/components/Dashboard.jsx:141`
- **现象**：`<StatusRow label="安全模式" value="只读" tone="readonly" />` 永远显示"只读"。GlobalStatusBar 切到 L3 后写 `localStorage['ai-plc:safety-level']`，Dashboard 不读。
- **影响**：用户切到 L3 后 Dashboard 仍显示"只读"，**安全边界误判**。A-3 修复 F-018 时未同步到 Dashboard。
- **分类**：收尾批次 A-3 修复不完整
- **严重级别**：HIGH

#### F-042: useConversation 非流式 fallback fetch 缺失 localControlHeaders
- **位置**：`src/hooks/useConversation.js:211-216`
- **现象**：SSE 失败回退到非流式 `/chat` 时 `headers: { 'Content-Type': 'application/json' }` 缺 `localControlHeaders()`，而 `streamChat` 和 `request()` 都会注入。
- **影响**：本地 API Token 鉴权开启时，SSE 失败后非流式 fallback 必失败（403 Forbidden），与流式主路径行为不一致。
- **分类**：原有问题
- **严重级别**：HIGH

#### F-056: SettingsPanel testResult.reply 渲染模型回复到 UI（F-024 残留）
- **位置**：`src/components/SettingsPanel.jsx:69`
- **现象**：`{testResult.reply && <span>"{testResult.reply}"</span>}` 直接渲染后端返回的 `reply` 字段。F-024 已标注"reply 可能包含敏感信息"，至今未修。
- **影响**：测试连接的模型回复（可能含 API Key 片段、内部提示）显示在 UI，截图分享时泄露。
- **分类**：原有问题（F-024 残留）
- **严重级别**：HIGH

### MEDIUM（16 项 — 建议修复）

#### F-043: 5 个工具页面 streamChat 调用未传 signal，无法中止
- **位置**：`CodeExplainer.jsx:56` / `IoTableGenerator.jsx:51` / `FaultDiagnosis.jsx:58` / `VariableAnalyzer.jsx:48` / `LadderGenerator.jsx:46`
- **现象**：4 个 streamChat 调用与 `generateLadder` 调用均未传 `signal` 参数。Batch 6 给 ChatArea 加了 AbortController，工具页未同步。
- **影响**：用户切走 tab 后请求仍在后台进行；`MainWorkspace` 用 `display:none` 保持挂载，无法通过 cleanup 中止。Token 持续消耗。
- **分类**：原有问题
- **严重级别**：MEDIUM

#### F-047: OrchestratorPanel 文件 870 行超 800 行阈值
- **位置**：`src/components/OrchestratorPanel.jsx`（870 行）
- **现象**：单文件包含主组件 + 8 个子组件 + 3 张中文映射表 + apiGet/apiPost/apiDelete helper + formatUptime。F-006 已标注"Batch 7/8 拆分"，至今未拆。
- **影响**：超过 CLAUDE.md 800 行阈值；可维护性差；`useState` 共 13 个散落。
- **分类**：原有问题（F-006 残留）
- **严重级别**：MEDIUM

#### F-052: DiagnoseInspector 设备状态显示"待接入"但排查步骤静态硬编码
- **位置**：`src/layout/InspectorPanel.jsx:365-378`
- **现象**：排查步骤 1-5 全部硬编码（"检查 PLC 电源与连接"等），未根据 `messages` 中的 `warning`/`error` 内容生成针对性建议。
- **影响**：用户看到通用排查步骤会误以为是针对当前故障的诊断。误导性。
- **分类**：收尾批次 D-3 引入
- **严重级别**：MEDIUM

#### F-053: VariablesInspector 命名规范与地址分配硬编码
- **位置**：`src/layout/InspectorPanel.jsx:440-455`
- **现象**：硬编码"bXxx — Bool/iXxx — Int/rXxx — Real"命名规范 + "M0.0~M14.7/MW20~MW40/MD60~MD100"地址范围，与实际 `lastVars` 数据无关。
- **影响**：与 F-051 同类问题，假数据误导。
- **分类**：收尾批次 D-3 引入
- **严重级别**：MEDIUM

#### F-055: ErrorBoundary componentDidCatch console.error 不脱敏
- **位置**：`src/components/ErrorBoundary.jsx:15`
- **现象**：`console.error('[ErrorBoundary]', error, info.componentStack)` 把错误对象与组件栈完整打到控制台。
- **影响**：生产环境可能泄露内部路径/敏感 props（如 API Key 在 form state 中传入 SettingsPanel，渲染崩溃时 stack 可能包含 form 值）。
- **分类**：原有问题
- **严重级别**：MEDIUM

#### F-057: SettingsPanel handleTest 先调 updateSettings(form) 静默失败
- **位置**：`src/components/SettingsPanel.jsx:155`
- **现象**：`try { await updateSettings(form) } catch {}` 完全静默吞错。
- **影响**：保存失败时用户无感知，测试连接以旧配置运行，得到误导性结果。
- **分类**：原有问题
- **严重级别**：MEDIUM

#### F-058: OrchestratorPanel 教程弹窗与 RunDialog 未走 useFocusTrap/useEscClose
- **位置**：`OrchestratorPanel.jsx:688-720`（RunDialog）、`OrchestratorPanel.jsx:735-837`（TutorialModal）、`AppShell.jsx:277-302`（About）
- **现象**：F-015 收尾批次给 5 个弹窗加了 useFocusTrap，但 RunDialog/TutorialModal/About 三个弹窗未加；useEscClose 也未应用。
- **影响**：可访问性不一致；Tab 键可跳到弹窗外；Esc 不能关。F-016 修复目标"6 个弹窗"实际只覆盖 5 个。
- **分类**：收尾批次遗漏
- **严重级别**：MEDIUM

#### F-064: PromptTemplateModal 变量替换用 String.replace 不防转义
- **位置**：`src/components/PromptTemplateModal.jsx:46-49`
- **现象**：`content.replace(\`{${k}}\`, v)` 只替换第一个匹配；用户输入 `v` 含 `$&`/`$$` 等特殊模式字符会被错误解释。
- **影响**：模板变量替换不完整/不安全；工业 prompt 中变量重复出现常见。
- **分类**：原有问题
- **严重级别**：MEDIUM

#### F-066: PrimarySidebar 删除对话用 inline 二次确认而非 ConfirmDialog
- **位置**：`src/layout/PrimarySidebar.jsx:285-312`
- **现象**：删除对话按钮点击后 inline 显示"确认删除对话 / 取消"两个按钮，未用已存在的 `ui/ConfirmDialog`。
- **影响**：A-2 修复 F-017 时仅在 ConfirmDialog 内加了 `dangerAction` 支持，但 PrimarySidebar 未实际调用 ConfirmDialog。Focus trap/Esc/A11y 全无。F-017 修复不完整。
- **分类**：收尾批次 A-2 修复不完整
- **严重级别**：MEDIUM

#### F-069: 无 Zod/Schema 校验，API 响应直接解构使用
- **位置**：全局，如 `useConversation.js:62-68`、`InspectorPanel.jsx:267-273`
- **现象**：所有 API 响应直接 `d.conversations || []` 解构，无 schema 校验。
- **影响**：后端字段变更时前端静默失败显示空状态，无显式错误。违反 CLAUDE.md 输入验证原则。
- **分类**：原有问题
- **严重级别**：MEDIUM

#### F-070: 9 个 catch {} 完全静默吞错
- **位置**：`api.js:180`、`AppShell.jsx:46/50`、`useConversation.js:30`、`GlobalStatusBar.jsx:35/112`、`useWorkbenchHistory.js:23/31/38`、`PrimarySidebar.jsx:157`、`SettingsPanel.jsx:155`
- **现象**：9 处 `catch {}` 无任何错误处理或日志。
- **影响**：违反 CLAUDE.md 错误处理原则"永远不要静默吞掉错误"。
- **分类**：原有问题
- **严重级别**：MEDIUM

#### F-075: ChatArea CitationMessage 用 `window.open(url, '_blank')` 但未加 `rel="noopener noreferrer"`
- **位置**：`src/components/ChatArea.jsx:393-398`
- **现象**：`window.open(url, '_blank')` 无 noopener；同文件 `<a>` 标签（`:445`）正确加了 `rel="noopener noreferrer"`。
- **影响**：新窗口可通过 `window.opener` 访问原窗口，存在反向 tabnabbing 风险。
- **分类**：收尾批次 D-1 引入
- **严重级别**：MEDIUM

#### F-078: ChatArea useEffect scrollIntoView 在 messages 变化时强制滚动，打断用户回看
- **位置**：`src/components/ChatArea.jsx:660-662`
- **现象**：每次 `messages` 变化（含 streaming 中每个 token）都强制 `scrollIntoView`，不判断 `atBottom` 状态。
- **影响**：streaming 中用户往上滚动回看时，每个 token 到达都把视图拉回底部。
- **分类**：Batch 6 引入
- **严重级别**：MEDIUM

#### F-080: GlobalStatusBar PLC/TIA/PLCSIM 用服务器名字正则推断，非真实状态
- **位置**：`src/layout/GlobalStatusBar.jsx:40-53`
- **现象**：`matchServers` 用 `/plcsim|plc.sim/i`、`/tia/i`、`/plc|s7/i` 正则匹配服务器名。
- **影响**：服务器命名变化时状态推断会错。D-4 宣称"接入真实 API"，实际是"按名字猜"。
- **分类**：收尾批次 D-4 实现方式
- **严重级别**：MEDIUM

#### F-086: CSP `script-src 'unsafe-inline'` 未迁移到 nonce-based
- **位置**：`index.html:12`
- **现象**：`script-src 'self' 'unsafe-inline'` — 注释明确"生产构建后可改用 nonce-based CSP"，未改。
- **影响**：`'unsafe-inline'` 削弱 CSP 防 XSS 能力。
- **分类**：F-022 Batch 2 已放宽，收紧未完成
- **严重级别**：MEDIUM

#### F-087: useConversation handleSend 依赖 messages 导致每次消息变化重建
- **位置**：`src/hooks/useConversation.js:258`
- **现象**：`handleSend` 的 `useCallback` 依赖数组含 `messages`，每次消息变化（streaming 中每个 token）`handleSend` 重新创建。
- **影响**：`ChatArea` 接 `onSend={handleSend}` 重渲染频繁，streaming 中可能卡顿。应改用 `setMessages(prev => ...)` 内访问最新 messages。
- **分类**：Batch 6 引入
- **严重级别**：MEDIUM

#### F-062: useTabs closeTab 在 StrictMode 双调用下可能 setActiveTab 两次（与 F-037 合并看待）
- **位置**：`src/hooks/useTabs.js:28-38`
- **现象**：F-037 已记录的 updater 内副作用反模式，叠加 `main.jsx:7` 的 `<React.StrictMode>`。React 18 StrictMode 双调用 reducer/updater，`setActiveTab` 会被调用两次。
- **影响**：当前 `setActiveTab` 是幂等的，无实际 bug。但仍是反模式，React 19 严格模式可能告警。
- **分类**：F-037 子项
- **严重级别**：MEDIUM（与 F-037 合并看待）

#### F-090: 4 个工具页 streamChat 调用未传 abort signal（与 F-043 合并）
- **位置**：见 F-043
- **现象**：F-043 子项，强调 4 个工具页无停止按钮，用户无法中止生成。
- **影响**：与 F-043 同。
- **分类**：F-043 衍生
- **严重级别**：MEDIUM（合并到 F-043）

### LOW（25 项 — 可选修复）

#### F-044: OrchestratorPanel 直接 fetch 三处绕过 api.js request 封装
- **位置**：`src/components/OrchestratorPanel.jsx:101-117`
- **现象**：自封装 `apiGet`/`apiPost`/`apiDelete` 绕过 `api.js:20` 的 `request()`。F-020 已记录未修。
- **影响**：维护成本高；`request()` 升级时不受益。
- **分类**：原有问题
- **严重级别**：LOW

#### F-045: RobotPanel 直接 fetch 第四处绕过 api.js 且重复定义 LOCAL_API_TOKEN
- **位置**：`src/components/RobotPanel.jsx:24` + `:132-139`
- **现象**：`LOCAL_API_TOKEN` 与 `api.js:14` 重复定义；`api.js` 已有 `runWorkflow()` 函数。
- **影响**：双份 Token 解析逻辑；违反 DRY。
- **分类**：原有问题（F-020 子项）
- **严重级别**：LOW

#### F-046: alert() 用于用户错误反馈，不符合工业 IDE 体验
- **位置**：`LadderGenerator.jsx:24` + `ChatArea.jsx:82`
- **现象**：用浏览器原生 `alert()` 显示导出失败，未复用 `ui/ConfirmDialog`/`ErrorState`。
- **影响**：阻塞 UI；与 VS Code 风格不符；Electron 中可能显示成原生对话框。
- **分类**：原有问题
- **严重级别**：LOW

#### F-048: ChatArea 文件 734 行接近阈值
- **位置**：`src/components/ChatArea.jsx`（734 行）
- **现象**：13 个消息组件 + ChatInput + 主组件 + 2 个工具函数。
- **影响**：未到 800 行但接近；建议拆分 `components/messages/` 子目录。
- **分类**：Batch 6 + 收尾批次累积
- **严重级别**：LOW

#### F-049: InspectorPanel 文件 538 行且包含 9 个 Inspector 子组件
- **位置**：`src/layout/InspectorPanel.jsx`（538 行）
- **现象**：9 个 Inspector 子组件 + PanelSection/KeyValue + 主组件。D-3 一次性塞入。
- **影响**：内聚度低；建议按 tab 拆分为 `layout/inspectors/`。
- **分类**：收尾批次 D-3 引入
- **严重级别**：LOW

#### F-054: LadderInspector PLC 规范 fallback 硬编码 'S7-1200'/'V18'
- **位置**：`src/layout/InspectorPanel.jsx:255-260`
- **现象**：`v={currentProject?.plc_type || 'S7-1200'}` 与 `v={currentProject?.tia_version || 'V18'}`，无项目时显示具体型号。
- **影响**：用户未选项目时误以为已默认选中。其他 Inspector 正确处理为"未选择"，不一致。
- **分类**：收尾批次 D-3 引入
- **严重级别**：LOW

#### F-059: AppShell 关于弹窗（About）未走统一 Modal 体系
- **位置**：`src/layout/AppShell.jsx:277-302`
- **现象**：内联 `<div className="fixed inset-0 ...">`，未用 `ui/ConfirmDialog`/`ui/Modal`；无 `role="dialog"`/`aria-modal`。
- **影响**：可访问性差；与 ConfirmDialog 模式不一致。
- **分类**：原有问题
- **严重级别**：LOW

#### F-060: LadderVisualizer 全部用 inline style，未走设计系统
- **位置**：`src/components/LadderVisualizer.jsx:10-23`（COLORS 常量）+ 全文 `style={{ ... }}`
- **现象**：颜色硬编码在 COLORS 常量与 inline style，未引用 `tokens.css`。
- **影响**：与设计 token 体系脱节；主题切换无法生效。
- **分类**：原有问题
- **严重级别**：LOW

#### F-061: OrchestratorPanel 工作流列表与工具列表用 `key={name}` 但名称可能重复
- **位置**：`OrchestratorPanel.jsx:412/515/528`
- **现象**：步骤列表用 `key={i}` 数组索引；工作流列表与工具列表用 `key={name}`。F-040 已修 ChatArea，此处未同步。
- **影响**：步骤重排/删除时可能复用错误 DOM。
- **分类**：原有问题
- **严重级别**：LOW

#### F-063: MainWorkspace 用 display:none 保持挂载，5 个工具页 useEffect 持续轮询
- **位置**：`MainWorkspace.jsx:82-92` + `Dashboard.jsx:92-99` + `GlobalStatusBar.jsx`
- **现象**：所有 tab 同时挂载，Dashboard/GlobalStatusBar 在 mount 时调多个 API。
- **影响**：内存占用累积；对工业 IDE 可接受，但若工具页改为轮询则问题。
- **分类**：Batch 4 设计决策
- **严重级别**：LOW

#### F-065: CreateProjectDialog 按 Enter 提交但未阻止表单默认行为
- **位置**：`src/components/CreateProjectDialog.jsx:38`
- **现象**：`onKeyDown` 调 `handleSubmit` 未 `e.preventDefault()`。
- **影响**：当前无 form 包裹无 bug；模式不严谨。
- **分类**：原有问题
- **严重级别**：LOW

#### F-071: InspectorPanel parseContent 函数局部定义两次
- **位置**：`InspectorPanel.jsx:268-272` + `:417-421`
- **现象**：两个 Inspector 各自定义相同的 `parseContent`，与 `ChatArea.jsx:50-61` 三份重复。
- **影响**：违反 DRY；建议提取到 `src/utils/parseContent.js`。
- **分类**：收尾批次 D-3 引入
- **严重级别**：LOW

#### F-072: ChatArea handleExport 与 LadderGenerator doExport 重复
- **位置**：`ChatArea.jsx:70-84` + `LadderGenerator.jsx:15-25`
- **现象**：两处定义几乎相同的 export 函数，均含 `alert('导出失败: ...)`。
- **影响**：DRY 违反；F-046 的 alert 问题两处都需修。
- **分类**：原有问题
- **严重级别**：LOW

#### F-073: useWorkbenchHistory save 用 Date.now().toString() 作 id，并发保存可能冲突
- **位置**：`src/hooks/useWorkbenchHistory.js:17`
- **现象**：同一毫秒内连续 `save` 两次会产生相同 id。
- **影响**：React 18 自动 batching 下同一事件回调中多次 setHistory 可能用同一 id，列表 key 冲突。
- **分类**：原有问题
- **严重级别**：LOW

#### F-074: ChatArea 用户消息无 ReactMarkdown 渲染，AI 消息有，渲染不一致
- **位置**：`src/components/ChatArea.jsx:517-518`
- **现象**：用户消息用 `whitespace-pre-wrap` 纯文本，AI 消息走 `<ReactMarkdown>`。
- **影响**：用户 markdown 语法显示原样字符。也是 XSS 防护，可接受。
- **分类**：设计决策
- **严重级别**：LOW

#### F-076: OrchestratorPanel RunDialog/TutorialModal 用 `bg-black/90` 而 ConfirmDialog 用 `modal-backdrop`
- **位置**：`OrchestratorPanel.jsx:698/737` vs `ui/ConfirmDialog.jsx:65`
- **现象**：弹窗背景遮罩类名不统一。
- **影响**：视觉不一致；z-index 管理混乱。
- **分类**：原有问题
- **严重级别**：LOW

#### F-077: ChatArea messages.map key 用 `msg.id || ${i}-${msg.role}` fallback 仍含索引
- **位置**：`src/components/ChatArea.jsx:704`
- **现象**：F-040 修复加了 `msg.id` 优先，但 fallback 仍用 `${i}-${msg.role}`。`useConversation.js` 所有分支都已加 id，fallback 是死代码。
- **影响**：实际不会触发，但代码读起来像"索引 key 仍可能"，误导后来者。
- **分类**：收尾批次 B-3 修复不彻底
- **严重级别**：LOW

#### F-079: BottomPanel useEffect scrollIntoView 在 filteredLogs 变化时强制滚动
- **位置**：`src/layout/BottomPanel.jsx:64-68`
- **现象**：与 F-078 同类问题：日志面板切 tab 或新日志到达时强制滚到底。
- **影响**：打断用户回看。
- **分类**：收尾批次 D-2 引入
- **严重级别**：LOW

#### F-081: InspectorPanel ChatInspector ragSources 取值边缘场景
- **位置**：`InspectorPanel.jsx:148` + `useConversation.js:155`
- **现象**：SSE 出错且非流式 fallback 也失败时，错误消息无 `rag_sources`，Inspector 显示"当前对话未引用知识库"。
- **影响**：边缘场景，Inspector 显示与实际错误状态不匹配。
- **分类**：收尾批次 D-3 引入
- **严重级别**：LOW

#### F-082: 缺少 ErrorBoundary 包裹 OrchestratorPanel/RobotPanel 等业务组件
- **位置**：`src/layout/AppShell.jsx:157`
- **现象**：ErrorBoundary 是顶层一个，业务组件崩溃都整页重置。
- **影响**：单组件崩溃影响全局；工业 IDE 期望单 tab 崩溃不影响其他 tab。
- **分类**：原有问题
- **严重级别**：LOW

#### F-083: PrimarySidebar SYSTEM_ITEMS 中 robot 与 orchestrator 用同一 Cpu 图标
- **位置**：`src/layout/PrimarySidebar.jsx:117-119`
- **现象**：`{ id: 'orchestrator', icon: Cpu }` 和 `{ id: 'robot', icon: Cpu }` 同图标。
- **影响**：用户视觉混淆。
- **分类**：Batch 4 迁移引入
- **严重级别**：LOW

#### F-084: MenuBar 编辑菜单 5 项全部 disabled，仍占菜单空间
- **位置**：`src/layout/MenuBar.jsx:24-32`
- **现象**：F-014 已记录，至今未移除或实现。
- **影响**：用户点击"编辑"看到全灰菜单。
- **分类**：F-014 残留
- **严重级别**：LOW

#### F-085: 8 个 Ctrl 快捷键标注未实现（F-013 残留）
- **位置**：`src/layout/MenuBar.jsx:17-31`
- **现象**：菜单标注 `Ctrl+N/Z/Y/X/C/V` 6 个快捷键，`AppShell.jsx:128-137` 只实现 `Ctrl+B/J/\`` 3 个。
- **影响**：用户期望 Ctrl+N 新建项目，实际无效。
- **分类**：F-013 残留
- **严重级别**：LOW

#### F-088: OrchestratorPanel useEffect 不清理，卸载后 setState 可能告警
- **位置**：`src/components/OrchestratorPanel.jsx:206`
- **现象**：`useEffect(() => { fetchAll() }, [fetchAll])` 内多个 setState 在卸载后仍可能被调用。
- **影响**：React 18 不再告警，但仍是反模式；切走 tab 后不卸载，影响小。
- **分类**：原有问题
- **严重级别**：LOW

#### F-089: ChatArea textarea 自动调整高度未实现
- **位置**：`src/components/ChatArea.jsx:604-612`
- **现象**：textarea `rows={1}` + `min-h-[38px] max-h-32`，无 `onInput` 自动调整高度逻辑。
- **影响**：用户输入多行时 textarea 不会长高。VS Code 风格输入区通常会自动长高。
- **分类**：Batch 6 引入
- **严重级别**：LOW

### 复审统计

| 级别 | 数量 | 编号范围 |
|------|------|----------|
| HIGH | 6 | F-050, F-051, F-067, F-068, F-042, F-056 |
| MEDIUM | 16 | F-043, F-047, F-052, F-053, F-055, F-057, F-058, F-064, F-066, F-069, F-070, F-075, F-078, F-080, F-086, F-087, F-062（合并 F-037）, F-090（合并 F-043） |
| LOW | 25 | F-044, F-045, F-046, F-048, F-049, F-054, F-059, F-060, F-061, F-063, F-065, F-071, F-072, F-073, F-074, F-076, F-077, F-079, F-081, F-082, F-083, F-084, F-085, F-088, F-089 |
| **合计** | **47** | F-042 ~ F-090 |

---

## 待补充
随着各 Batch 推进，继续记录其他发现。
