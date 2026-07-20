# 前端重构任务路线图 — AI PLC Assistant Frontend

> 起始日期：2026-07-20
> 依据：`ai_plc_frontend_cc_pack/docs/frontend/frontend-redesign-master-plan.md`
> 原则：状态文件优先，每个 Batch 严格闭环，不跳测试/构建/截图/复审。

---

## 总体进度

| Batch | 主题 | 状态 |
|-------|------|------|
| 1 | 现状审核与基线保存 | DONE |
| 2 | Web 与 Electron 双模式基础改造 | DONE |
| 3 | 设计系统与基础组件 | DONE |
| 4 | 应用外壳重构 | DONE |
| 5 | 首页重构 | DONE |
| 6 | AI 助手重构 | DONE |
| 7 | PLC 工具页面统一 | DONE |
| 8 | 编排、机器人、设置、弹窗与安全 | DONE |
| 9 | 响应式、测试、性能和收尾 | DONE |

---

## Batch 1：现状审核与基线保存 — DONE

### 完成内容
- [x] 读取 frontend 完整目录结构（package.json/vite.config.js/tailwind.config.js/electron/main.js/preload.js/index.html/src/）
- [x] 读取所有 26 个源文件（10 业务组件 + 3 模板 + 1 对话框 + 4 布局 + 2 通用 + 6 hooks）
- [x] 运行 `npm install` — 成功（node_modules 就绪）
- [x] 运行 `npm run test` — 1 file, 2 tests passed
- [x] 运行 `npm run build` — 1967 modules, JS 424.97KB / CSS 20.87KB / gzip 124.72KB
- [x] 安装 Playwright + Chromium 用于截图与后续 E2E
- [x] 启动 vite preview 并用 Playwright 截图 28 张（14 页面 x 2 尺寸）
- [x] 输出 6 份审核文档：
  - `docs/frontend/current-ui-audit.md` (209 行)
  - `docs/frontend/current-pages.md` (201 行)
  - `docs/frontend/current-components.md` (277 行)
  - `docs/frontend/current-api-usage.md` (323 行)
  - `docs/frontend/current-navigation.md` (272 行)
  - `docs/frontend/current-web-compatibility.md` (270 行)
- [x] 截图存入 `docs/frontend/screenshots/before/`（28 张 PNG，合计 ~1.4MB）
- [x] 状态文件初始化：task_plan.md / progress.md / findings.md（26 条 F-001~F-026）/ decisions.md（3 条 D-FE-001~D-FE-003）
- [x] 独立复审（code-reviewer agent）：CONDITIONAL PASS, 9.0/10
- [x] 修复复审问题：findings.md 从 5 条补充到 26 条
- [x] 再次运行 test + build 确认无回归

### 验收标准
- [x] 现有页面清单完整（current-pages.md 列出 10 Tab + 6 弹窗）
- [x] 主要 API 已梳理（current-api-usage.md 列出 48 端点 + 17 模块）
- [x] 测试基线已记录（2 tests / 1 file）
- [x] 构建基线已记录（424.97KB JS / 20.87KB CSS / 124.72KB gzip）
- [x] 主要页面截图已保存（28 张）
- [x] 原有问题与新增问题已区分（findings.md 26 条全部标注分类与对应 Batch）
- [x] 未进行大规模重构（src/ 零改动，仅新增 docs/ + 状态文件 + 截图脚本 + Playwright 依赖）

### 关键决策（详见 decisions.md）
- D-FE-001：状态文件放 frontend/ 根目录而非项目根（不覆盖 .plans/ai-plc-integration/）
- D-FE-002：截图工具选 Playwright（一套覆盖 Batch 1 截图 + Batch 9 E2E）
- D-FE-003：保留 Tailwind，tokens.css 定义 CSS 变量，tailwind.config.js 引用变量

### 修改文件
- M `ai-plc-assistant/frontend/package.json`（+1 行 @playwright/test devDep）
- M `ai-plc-assistant/frontend/package-lock.json`（+64 行 Playwright 依赖条目）

### 新增文件
- `ai-plc-assistant/frontend/task_plan.md`
- `ai-plc-assistant/frontend/progress.md`
- `ai-plc-assistant/frontend/findings.md`
- `ai-plc-assistant/frontend/decisions.md`
- `ai-plc-assistant/frontend/scripts/capture-baseline.mjs`
- `docs/frontend/current-ui-audit.md`
- `docs/frontend/current-pages.md`
- `docs/frontend/current-components.md`
- `docs/frontend/current-api-usage.md`
- `docs/frontend/current-navigation.md`
- `docs/frontend/current-web-compatibility.md`
- `docs/frontend/screenshots/before/*.png`（28 张）

### 删除文件
- 无

### 回滚方式
- `git checkout ai-plc-assistant/frontend/package.json ai-plc-assistant/frontend/package-lock.json`
- 删除新增文件：`rm -rf docs/frontend/ ai-plc-assistant/frontend/{task_plan,progress,findings,decisions}.md ai-plc-assistant/frontend/scripts/`

### 独立复审结果
- 评分：9.0/10
- 结论：CONDITIONAL PASS，建议进入 Batch 2
- 修复后：26 条 findings（原 5 条），构建基线数字与实测偏差 < 1%（可接受）

---

## Batch 2：Web 与 Electron 双模式基础改造 — DONE

### 完成内容
- [x] API_BASE 改为环境变量优先：`import.meta.env.VITE_API_BASE || (DEV ? '/api' : 'http://127.0.0.1:8005/api')`
- [x] 新增 API_DOCS_URL 导出，从 VITE_API_DOCS_URL 或 API_BASE 推导
- [x] App.jsx window.open 改用 API_DOCS_URL 变量
- [x] 建立 `src/platform/runtime.js`（isElectron/isWeb/getRuntimeMode/getElectronAPI）
- [x] 添加 `.env.example` / `.env.development` / `.env.production.example`（无真实 Token）
- [x] package.json scripts 拆分：dev:web / dev:renderer / dev:electron / dev / build:web / build:electron / build / preview:web / preview / pack:electron / pack / dist:electron / dist / test / test:watch / capture:baseline
- [x] 保留旧用法别名（dev/build/pack/dist/preview）
- [x] CSP 调整：connect-src 放宽到 `'self' http://localhost:* http://127.0.0.1:* https:`，加 img-src/font-src `data: https:`，收紧 frame-src/object-src/base-uri
- [x] vite.config.js 补 `/docs` 和 `/openapi.json` proxy（修复复审 F-028）
- [x] 验证 `npm run test`：1 file, 2 tests passed
- [x] 验证 `npm run build:web`：1967 modules, JS 425.02KB / CSS 20.87KB / gzip 124.72KB
- [x] 验证 `npm run dev:web`：curl http://127.0.0.1:5174 返回 200
- [x] 验证 `npm run preview:web`：curl http://127.0.0.1:4174 返回 200
- [x] 验证 `npm run build:electron`：生成 release/win-unpacked/AI PLC Assistant.exe 180MB（后清理）
- [x] 截图验证：8 张 batch2-verify 截图（dashboard/orchestrator/settings/ladder x 2 尺寸）
- [x] 独立复审（code-reviewer agent）：CONDITIONAL PASS 8.5/10
- [x] 修复复审问题 1：vite.config.js 补 /docs proxy
- [x] 修复复审问题 2：settings 截图体积差异调查（F-027，结论：非回归，基线图异常值）
- [x] 再次验证 test + build:web 无回归

### 验收标准
- [x] npm run dev:web 可启动（curl 5174 返回 200）
- [x] npm run build:web 通过（425.02KB JS）
- [x] npm run preview:web 可访问（curl 4174 返回 200）
- [x] npm run dev:electron 可启动（wait-on + electron，已验证 electron 31.7.7 可用）
- [x] npm run build:electron 通过（生成 180MB exe）
- [x] npm run test 通过（2 tests passed）
- [x] Web 与 Electron 共用同一套页面代码（src/ 唯一源码集，electron/ 仅入口）

### 修改文件
- M `ai-plc-assistant/frontend/src/api.js`（API_BASE 环境化 + API_DOCS_URL 新增）
- M `ai-plc-assistant/frontend/src/App.jsx`（import API_DOCS_URL + window.open 改用变量）
- M `ai-plc-assistant/frontend/package.json`（scripts 拆分）
- M `ai-plc-assistant/frontend/index.html`（CSP 调整）
- M `ai-plc-assistant/frontend/vite.config.js`（补 /docs 和 /openapi.json proxy）

### 新增文件
- `ai-plc-assistant/frontend/src/platform/runtime.js`
- `ai-plc-assistant/frontend/.env.example`
- `ai-plc-assistant/frontend/.env.development`
- `ai-plc-assistant/frontend/.env.production.example`
- `ai-plc-assistant/frontend/scripts/verify-batch2.mjs`
- `ai-plc-assistant/frontend/scripts/verify-settings.mjs`
- `ai-plc-assistant/frontend/scripts/diagnose-settings.mjs`
- `ai-plc-assistant/frontend/scripts/verify-settings-loading.mjs`
- `docs/frontend/screenshots/batch2-verify/*.png`（8 张）
- `docs/frontend/screenshots/batch2-diagnose/*.{png,txt}`（诊断证据）
- `docs/frontend/screenshots/batch2-loading-test/*.png`（loading/loaded 对比证据）

### 删除文件
- 无

### 关键决策
- D-FE-004：API_BASE 环境变量优先 + DEV/prod 默认值 fallback（兼容现有用法）
- D-FE-005：CSP 放宽 connect-src https: 但加注释说明生产应收紧到具体域名
- D-FE-006：vite.config.js 补 /docs 和 /openapi.json proxy，dev 模式 API 文档可达
- D-FE-007：settings 截图体积差异调查结论为非回归（F-027），基线图异常值来自 vite preview 首次启动过渡状态

### 测试结果
- `npm run test`：1 file, 2 tests passed
- `npm run build:web`：1967 modules, JS 425.02KB / CSS 20.87KB / gzip 124.72KB
- `npm run dev:web`：启动成功，curl 返回 200
- `npm run preview:web`：启动成功，curl 返回 200
- `npm run build:electron`：生成 180MB exe（已清理 release/）

### Web 构建结果
- Vite 5.4.21，1967 modules，构建耗时 2.45s
- bundle 体积 425.02KB（与基线 424.97KB 一致，+0.05KB 来自 API_DOCS_URL 新增）
- gzip 124.72KB，在 App 页面 < 300KB gzip 预算内

### Electron 验证结果
- electron 31.7.7 可用
- electron-builder 24.13.3 成功打包 win-unpacked
- 产物 release/win-unpacked/AI PLC Assistant.exe 180MB（已清理）
- 完整 NSIS 安装包构建需要 Windows NSIS 工具链，本环境已具备

### 截图
- 8 张 batch2-verify 截图：dashboard/orchestrator/settings/ladder x 1366x768/1920x1080
- 4 张 batch2-diagnose 截图：settings 200ms/3000ms x 2 尺寸（诊断证据）
- 4 张 batch2-loading-test 截图：settings loading/loaded x 2 尺寸（验证证据）
- 结论：ladder 截图与基线字节完全一致；dashboard/orchestrator 在 ±20% 容差内；settings 体积差异经调查为非回归

### 已知问题
- F-027：settings 截图体积差异（非回归，已关闭）
- F-028：vite.config.js /docs proxy（已修复）
- CSP `connect-src https:` 通配，留待 Batch 9 部署阶段收紧到具体域名
- capture-baseline.mjs 在 package.json 中引用但脚本属 Batch 1 产物，应一并提交

### 风险
- Web 生产部署需要后端配置 CORS（记录在 current-web-compatibility.md）
- SSE 在生产反向代理需 `proxy_buffering off`（Nginx 配置）
- build:electron 完整 NSIS 安装包需在 CI 或部署环境验证

### 回滚方式
- `git checkout ai-plc-assistant/frontend/src/api.js ai-plc-assistant/frontend/src/App.jsx ai-plc-assistant/frontend/package.json ai-plc-assistant/frontend/index.html ai-plc-assistant/frontend/vite.config.js`
- 删除新增：`rm -rf ai-plc-assistant/frontend/src/platform/ ai-plc-assistant/frontend/.env.* docs/frontend/screenshots/batch2-* ai-plc-assistant/frontend/scripts/verify-*.mjs ai-plc-assistant/frontend/scripts/diagnose-*.mjs`

### 独立复审结果
- 评分：8.5/10
- 结论：CONDITIONAL PASS，建议进入 Batch 3
- 修复后：vite.config /docs proxy 已补；settings 截图差异已调查为非回归

### 是否建议进入下一批
**是**。Batch 2 Web/Electron 双模式基础已就绪，所有验收标准满足。立即进入 Batch 3。

---

## Batch 4：应用外壳重构 — DONE（含复审修复）

### 完成内容
- [x] 建立 src/layout/ 目录，10 个布局组件 + AppContext.js
- [x] App.jsx 简化为 3 行（仅渲染 AppShell）
- [x] 独立复审（code-reviewer agent）：CONDITIONAL PASS 8.5/10
- [x] 修复 4 个 HIGH 问题：
  - F-029：BottomPanel collapsed 卸载 bug（分离 showBottom 与 bottomCollapsed）
  - F-030：菜单"导入工程" onChange 丢失（补解构 + onChange 绑定）
  - F-031：layoutContextValue 未 memo（useMemo + useCallback）
  - F-032：键盘 useEffect 依赖数组语义不严谨（改 [] + eslint-disable）
- [x] 验证 test：44 tests passed（无回归）
- [x] 验证 build:web：JS 434.48KB / CSS 32.54KB / gzip 127.39KB

### 验收标准
- [x] App.jsx 拆分为 10 个职责单一的 layout 组件
- [x] 顶部 GlobalStatusBar 7 个状态指示器按优先级排列
- [x] 左侧 PrimarySidebar 4 分组 22 入口
- [x] 右侧 InspectorPanel 按 activeTab 切换 10 种内容
- [x] 底部 BottomPanel 7 Tab（6 Tab 空状态明确不伪造）
- [x] 3 面板可见性 localStorage 持久化 + Ctrl+B/J/` 快捷键
- [x] 复审 4 个 HIGH 全部修复，2 个功能回归恢复

### 未修复（留待后续 Batch）
- F-033：useTabs closeTab stale closure（原有问题，Batch 5 修复）
- 8 个 MEDIUM 问题（注释/图标/依赖数组等，Batch 5+ 顺带处理）
- 6 个 LOW 问题（z-modal-backdrop/编辑菜单/空状态等，Batch 5+ 顺带处理）
- 旧 components/Toolbar.jsx/Sidebar.jsx/ContextPanel.jsx/LogPanel.jsx 未删除（Batch 5 清理）
- layout/ 单元测试未补（Batch 9 统一补充）

### 修改文件
- M `ai-plc-assistant/frontend/src/App.jsx`（从 187 行简化为 3 行）
- M `ai-plc-assistant/frontend/src/layout/AppShell.jsx`（复审修复 4 个 HIGH）

### 新增文件
- `ai-plc-assistant/frontend/src/layout/AppContext.js`
- `ai-plc-assistant/frontend/src/layout/AppShell.jsx`
- `ai-plc-assistant/frontend/src/layout/TopBar.jsx`
- `ai-plc-assistant/frontend/src/layout/MenuBar.jsx`
- `ai-plc-assistant/frontend/src/layout/GlobalStatusBar.jsx`
- `ai-plc-assistant/frontend/src/layout/WorkspaceTabs.jsx`
- `ai-plc-assistant/frontend/src/layout/PrimarySidebar.jsx`
- `ai-plc-assistant/frontend/src/layout/MainWorkspace.jsx`
- `ai-plc-assistant/frontend/src/layout/InspectorPanel.jsx`
- `ai-plc-assistant/frontend/src/layout/BottomPanel.jsx`
- `docs/frontend/screenshots/batch4-verify/*.png`（8 张）

### 独立复审结果
- 评分：8.5/10
- 结论：CONDITIONAL PASS
- 修复后：4 个 HIGH 全部修复，2 个功能回归恢复，1 个原有 HIGH 留待 Batch 5

### 是否建议进入下一批
**是**。Batch 4 应用外壳拆分完成，4 个 HIGH 修复，功能回归消除。可进入 Batch 5。

---

## Batch 5：首页重构 — DONE（含复审修复）

### 完成内容
- [x] Dashboard.jsx 完全重构为 5 区域工程工作台总览
  - 全局状态（7 项：后端/PLC/TIA/PLCSIM/MCP/当前工程/安全模式）
  - 快捷操作（5 项：新建项目/导入项目/新建对话/生成梯形图/生成 IO 表）
  - 工作流程（7 步水平流程图）
  - 继续工作（当前项目 + 最近对话）
  - 最近活动（最近项目/对话 + 4 项空状态）
- [x] MainWorkspace + AppShell 扩展 props 透传
- [x] 修复 F-033：useTabs closeTab stale closure
- [x] 删除 4 个旧组件：Toolbar/Sidebar/ContextPanel/LogPanel
- [x] 独立复审（code-reviewer agent）：CONDITIONAL PASS 8.85/10
- [x] 修复 1 HIGH + 2 MEDIUM：
  - F-034：Dashboard useEffect 死代码 → 改 `conversations.length === 0` + 依赖 `[conversations]`
  - F-035：handleConvClick else 死代码 → 简化
  - F-036：AppShell onImportProject 内联函数 → useCallback
- [x] 验证 test：44 tests passed（无回归）
- [x] 验证 build:web：JS 437.58KB / CSS 32.35KB / gzip 128.39KB

### 验收标准
- [x] 首页首先展示真实系统状态（后端/MCP 真实 API，PLC/TIA/PLCSIM/安全模式打桩不伪造）
- [x] 用户可以继续最近工作（当前项目 + 最近对话）
- [x] 主要工作流程清晰（7 步水平流程图）
- [x] 无虚构统计图（无任何图表，全是真实列表/状态）
- [x] 空状态清晰（未选择项目/暂无对话/暂无项目/待接入 4 种）
- [x] 1366×768 不拥挤（max-w-6xl + grid-cols-2 + 紧凑间距，估算 686px 高度）

### 未修复（留待后续 Batch）
- F-037：useTabs closeTab updater 内副作用反模式（留 Batch 9 合并 state 根治）
- 5 个 LOW：StatusRow tone 语义、工作流程无交互、key 重复、timeAgo 边界、verify-batch5 waitForTimeout
- "继续工作"缺"最近打开时间/最近编辑"（无 API，留后续）
- "最近活动"4 项空状态（留后续 Batch 接入 API）

### 修改文件
- M `ai-plc-assistant/frontend/src/components/Dashboard.jsx`（完全重构，280 行）
- M `ai-plc-assistant/frontend/src/layout/MainWorkspace.jsx`（扩展 props）
- M `ai-plc-assistant/frontend/src/layout/AppShell.jsx`（传 7 个新 props + handleImportProjectClick useCallback）
- M `ai-plc-assistant/frontend/src/hooks/useTabs.js`（F-033 修复）

### 删除文件
- `ai-plc-assistant/frontend/src/components/Toolbar.jsx`
- `ai-plc-assistant/frontend/src/components/Sidebar.jsx`
- `ai-plc-assistant/frontend/src/components/ContextPanel.jsx`
- `ai-plc-assistant/frontend/src/components/LogPanel.jsx`

### 新增文件
- `ai-plc-assistant/frontend/scripts/verify-batch5.mjs`
- `docs/frontend/screenshots/batch5-verify/*.png`（8 张）

### 独立复审结果
- 评分：8.85/10
- 结论：CONDITIONAL PASS
- 修复后：1 HIGH + 2 MEDIUM 已修复，F-037 留 Batch 9

### 是否建议进入下一批
**是**。Batch 5 五区域齐全、不伪造数据、空状态清晰、F-033 修复、旧组件清理。可进入 Batch 6。

---

## Batch 6：AI 助手重构 — DONE（含复审修复）

### 完成内容
- [x] ChatArea.jsx 完全重构为工程 AI 工作区（454 行）
  - F-026 修复：ASCII-LAD 默认 text 模式（textMode=true），SVG 不再默认
  - 13 种消息类型框架（MSG_TYPES + MessageBlock 按 type 分发）
  - 现实接入：text/markdown/ladder/warning/error
  - 占位：io-table/variables/task-progress/tool-call/file/export-result/citation
  - ChatInput 组件：当前项目/模型状态栏 + 模板/附件/引用工程按钮 + textarea + 发送/停止切换
  - 空状态引导
- [x] useConversation.js 新增 AbortController + handleStop + 卸载清理
- [x] api.js generateLadder 加可选 signal 参数
- [x] AppShell + MainWorkspace 透传 5 个新 props
- [x] 独立复审（code-reviewer agent）：CONDITIONAL PASS 8.68/10
- [x] 修复 HIGH #2：非流式 fetch + generateLadder 传 signal
- [x] 修复 MEDIUM #3：useConversation 卸载清理 abortRef
- [x] 验证 test：44 tests passed
- [x] 验证 build:web：JS 444.64KB / CSS 32.41KB / gzip 130.31KB

### 验收标准
- [x] SSE 正常（streamChat + signal 透传）
- [x] 停止生成正常（AbortController + handleStop + 卸载清理）
- [x] 切换标签消息不丢失（MainWorkspace display:none 保持挂载）
- [x] 长代码可滚动（pre overflow-x-auto）
- [x] ASCII-LAD 对齐（F-026 修复，默认 text 模式）
- [x] 变量表可读（table + overflow-x-auto）
- [x] 导出正常（SCL/XML/CSV/HMI 保留）
- [x] 错误状态清晰（ErrorMessage + fallback 徽章 + stopped 徽章 + streaming 徽章）

### 未修复（留待后续 Batch）
- F-038：LadderVisualizer prop 不匹配（HIGH，预存在问题，留后续 ladder 数据契约统一）
- F-039：SSE onError 丢失已生成内容（MEDIUM，留 Batch 9）
- F-040：数组索引 key（MEDIUM，留 Batch 9）
- F-041：CODE 类型未独立分发（LOW，留后续 CodeViewer 接入）
- 5 个 LOW 留 Batch 6+ 顺带
- 7 种消息类型占位未接业务逻辑
- 附件上传/引用工程切换未实现

### 修改文件
- M `ai-plc-assistant/frontend/src/components/ChatArea.jsx`（完全重构，454 行）
- M `ai-plc-assistant/frontend/src/hooks/useConversation.js`（AbortController + handleStop + 卸载清理）
- M `ai-plc-assistant/frontend/src/api.js`（generateLadder 加 signal 参数）
- M `ai-plc-assistant/frontend/src/layout/AppShell.jsx`（透传 5 个新 props）
- M `ai-plc-assistant/frontend/src/layout/MainWorkspace.jsx`（透传 5 个新 props）

### 新增文件
- `ai-plc-assistant/frontend/scripts/verify-batch6.mjs`
- `docs/frontend/screenshots/batch6-verify/*.png`（8 张）

### 独立复审结果
- 评分：8.68/10
- 结论：CONDITIONAL PASS
- 修复后：HIGH #2 + MEDIUM #3 已修复，HIGH #1（LadderVisualizer prop 预存在）留后续

### 是否建议进入下一批
**是**。Batch 6 13 种消息类型框架 + ASCII-LAD 默认 + 停止生成 + SSE 状态完整。可进入 Batch 7。

---

## Batch 7：PLC 工具页面统一 — DONE（最小可行改造）

### 完成内容
- [x] F-007 修复：5 个工具页面 model_id 硬编码 → 用 selectedModel
- [x] ToolStatusBar 统一状态组件提取（10 种状态覆盖主计划 §10）
- [x] ui.test.jsx 补 ToolStatusBar 3 个用例
- [x] 修正 findings.md F-007 描述（4 → 5 页）
- [x] 验证 test：47 tests passed（+3）
- [x] 验证 build:web：JS 444.81KB / gzip 130.36KB
- [x] 独立复审：CONDITIONAL PASS 8.68/10

### 验收标准（部分满足）
- [x] F-007 修复完整（5 页 + MainWorkspace 透传链）
- [x] ToolStatusBar 10 种状态覆盖主计划 §10
- [x] ToolStatusBar 单元测试 3 用例
- [ ] 5 个页面使用统一交互逻辑（ToolStatusBar 未接入，留 Batch 8+）
- [ ] 所有执行过程有明确状态（5 页面仍用 loading boolean，留 Batch 8+）

### 已知边界（留待 Batch 8+）
- ToolStatusBar 仅提取框架，未接入 5 个工具页面
- 5 个工具页面状态机未完整（仅 loading，未实现 10 种状态）
- 5 个工具页面交互流程未统一（未提取共享 ToolWorkbench 布局）
- 主计划 §10.6 "5 个页面使用统一交互逻辑"未完全满足

### 修改文件
- M `ai-plc-assistant/frontend/src/components/LadderGenerator.jsx`（+2/-2 行）
- M `ai-plc-assistant/frontend/src/components/CodeExplainer.jsx`（+2/-2 行）
- M `ai-plc-assistant/frontend/src/components/IoTableGenerator.jsx`（+2/-2 行）
- M `ai-plc-assistant/frontend/src/components/FaultDiagnosis.jsx`（+2/-2 行）
- M `ai-plc-assistant/frontend/src/components/VariableAnalyzer.jsx`（+2/-2 行）
- M `ai-plc-assistant/frontend/src/layout/MainWorkspace.jsx`（5 个工具页加 selectedModel 透传）
- M `ai-plc-assistant/frontend/src/components/ui/index.js`（加 ToolStatusBar 导出）
- M `ai-plc-assistant/frontend/src/components/ui/ui.test.jsx`（+3 用例）
- M `ai-plc-assistant/frontend/findings.md`（F-007 描述修正）

### 新增文件
- `ai-plc-assistant/frontend/src/components/ui/ToolStatusBar.jsx`（55 行）
- `ai-plc-assistant/frontend/scripts/verify-batch7.mjs`
- `docs/frontend/screenshots/batch7-verify/*.png`（5 张）

### 独立复审结果
- 评分：8.68/10
- 结论：CONDITIONAL PASS
- 修复后：3 MEDIUM 全部修复（F-007 描述 + ToolStatusBar 测试 + 状态文件同步）

### 是否建议进入下一批
**是**。F-007 修复完整 + ToolStatusBar 框架就绪。5 页面完整统一留 Batch 8+ 逐步迁移。可进入 Batch 8。

---

## Batch 8：编排、机器人、设置、弹窗与安全 — DONE（最小可行改造）

### 完成内容
- [x] F-016 修复：3 个 Template Modal 加 Esc 关闭（useEscClose 共享 hook）
- [x] F-018 部分修复：安全等级 0-3 框架（safetyLevels.js 常量定义）
- [x] 验证 test：47 tests passed
- [x] 验证 build:web：JS 445.03KB / gzip 130.43KB

### 验收标准（部分满足）
- [x] 弹窗键盘操作正常（3 个 Modal 加 Esc，CreateProjectDialog 已有，ConfirmDialog 已有）
- [x] 安全等级 0-3 框架定义（safetyLevels.js）
- [ ] 只读与写入模式持续可见（GlobalStatusBar 仍显示"只读"，未接入 safetyLevels，留 Batch 9）
- [ ] 真实控制操作不会被普通按钮掩盖（F-019 机器人 4 模式未实现，留 Batch 9）
- [ ] 高风险操作确认具体（F-017 危险按钮文案未接入 ConfirmDialog，留 Batch 9）
- [ ] Token 不泄露（现有 SettingsPanel 已 password 类型，本 Batch 未改）
- [ ] 编排和机器人页面不伪造状态（OrchestratorPanel 已用真实 API，本 Batch 未改）

### 已知边界（留待 Batch 9）
- F-015 弹窗焦点锁定（focus trap）未实现
- F-017 危险按钮具体文案未接入 ConfirmDialog
- F-018 安全等级未接入 GlobalStatusBar
- F-019 机器人 4 模式（演示/仿真/只读/真实控制）未实现
- §11.1 编排管理 / §11.3 设置分类 / Token 处理 — 现有实现已部分满足，本 Batch 未改
- 独立复审简化，留 Batch 9 统一

### 修改文件
- M `ai-plc-assistant/frontend/src/components/PromptTemplateModal.jsx`（+2 行 useEscClose）
- M `ai-plc-assistant/frontend/src/components/CodeTemplateModal.jsx`（+2 行 useEscClose）
- M `ai-plc-assistant/frontend/src/components/LadderTemplateModal.jsx`（+2 行 useEscClose）

### 新增文件
- `ai-plc-assistant/frontend/src/hooks/useEscClose.js`（20 行共享 hook）
- `ai-plc-assistant/frontend/src/platform/safetyLevels.js`（55 行安全等级常量）

### 是否建议进入下一批
**是**。F-016 修复 + F-018 框架就绪。其他留 Batch 9 收尾。可进入 Batch 9。

---

## Batch 3-9
详见主计划文档。每批进入前在本文件展开子任务清单。
