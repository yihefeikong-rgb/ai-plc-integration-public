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

## 待补充
随着各 Batch 推进，继续记录其他发现。
