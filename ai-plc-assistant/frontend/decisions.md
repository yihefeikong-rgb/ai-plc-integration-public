# 前端重构架构决策记录 — AI PLC Assistant Frontend

> 起始日期：2026-07-20
> 原则：记录重要设计、架构、取舍选择及原因。

---

## D-FE-001：状态文件放在 frontend/ 根目录而非项目根

- **日期**：2026-07-20
- **背景**：项目级 `.plans/ai-plc-integration/` 已有 `task_plan.md`/`progress.md`/`findings.md`/`decisions.md` 记录整体协作层与各 Phase 进展。若直接覆盖会丢失历史记录。
- **选项**：
  - A. 覆盖 `.plans/ai-plc-integration/` 下同名文件
  - B. 在 `ai-plc-assistant/frontend/` 下新建任务级状态文件
  - C. 在 `docs/frontend/` 下新建状态文件
- **选择**：B — 在 `ai-plc-assistant/frontend/` 下新建
- **理由**：
  - 不覆盖项目级协作状态文件，保留历史决策可追溯
  - 状态文件与目标目录同位置，方便后续维护
  - `docs/frontend/` 留给审核文档与最终交付文档

## D-FE-002：截图工具优先 Playwright

- **日期**：2026-07-20
- **背景**：主计划 Batch 1 要求 1366x768 与 1920x1080 两尺寸截图 14 个页面，Batch 9 要求 E2E 测试。需要 headless 浏览器自动化。
- **选项**：
  - A. 使用 Electron 内置截图（仅能截 Electron 窗口，无法截 Web 模式）
  - B. 安装 Playwright 作为 devDependency，既做截图又做 E2E
  - C. 安装 Puppeteer（仅 Chromium，无 IE/WebKit 跨浏览器）
- **选择**：B — Playwright
- **理由**：
  - Playwright 是 TypeScript/JavaScript 生态主推 E2E 工具（参见 `rules/typescript/testing.md`）
  - 一套工具覆盖 Batch 1 截图与 Batch 9 E2E
  - 支持 Chromium/Firefox/WebKit 多浏览器
  - 原生支持 viewport 设置与截图 API
- **后果**：
  - 增加 devDependency 体积（约 200MB 浏览器二进制）
  - 需要 `npx playwright install chromium` 下载浏览器

## D-FE-003：保持 Tailwind 与新设计 tokens 共存

- **日期**：2026-07-20
- **背景**：项目已使用 Tailwind 3.4 + 自定义 ide/accent/text/status 色板。主计划 Batch 3 要求建立 `src/styles/` 目录与 tokens.css。
- **选项**：
  - A. 完全替换 Tailwind，改用纯 CSS tokens
  - B. 保留 Tailwind，在 tailwind.config.js 中引用 CSS 变量
  - C. 双系统并存，允许冲突
- **选择**：B — Tailwind 引用 CSS 变量
- **理由**：
  - 主计划明确"可与 Tailwind 配合，但不得维护两套相互冲突的颜色系统"
  - 保留 Tailwind 的 utility 优势，同时获得 CSS 变量的运行时可配置性
  - 现有 ide.* 色板已是语义化，迁移成本低
- **实现**：
  - `src/styles/tokens.css` 定义 `:root` CSS 变量
  - `tailwind.config.js` 引用变量：`colors: { ide: { bg: 'var(--color-ide-bg)' } }`
  - 旧类名保持兼容，不需要批量重写

---

## D-FE-004：API_BASE 环境变量优先 + DEV/prod 默认值 fallback

- **日期**：2026-07-20
- **背景**：Batch 2 需将 API_BASE 硬编码改为环境变量，但要兼容现有 dev/prod 用法。
- **选项**：
  - A. 仅用 `import.meta.env.VITE_API_BASE`，未配置时返回 undefined 导致 fetch 失败
  - B. `import.meta.env.VITE_API_BASE || (DEV ? '/api' : 'http://127.0.0.1:8005/api')`，fallback 到原默认值
  - C. 强制要求 .env 文件，否则构建失败
- **选择**：B — 环境变量优先 + DEV/prod 默认值 fallback
- **理由**：
  - 兼容现有用法（未配置 .env 时行为不变）
  - Web 部署可通过 .env.production 配置具体后端地址
  - Electron 同机后端默认 127.0.0.1:8005 仍可用
  - 不强制 .env 文件存在，降低使用门槛

## D-FE-005：CSP 放宽 connect-src https: 但加注释说明生产应收紧

- **日期**：2026-07-20
- **背景**：Batch 2 需让 Web 部署到 HTTPS 后端时 connect-src 不拦截，但通配 https: 等同信任所有 HTTPS 来源。
- **选项**：
  - A. 保持 `connect-src 'self' http://localhost:*`，Web 部署需用户手动改 CSP
  - B. 放宽到 `connect-src 'self' http://localhost:* http://127.0.0.1:* https:`，加注释说明生产应收紧
  - C. 用环境变量动态生成 CSP（需 HTML 模板引擎）
- **选择**：B — 放宽 https: 但加注释
- **理由**：
  - Web 部署到 HTTPS 后端立即可用，无需用户手改 CSP
  - 注释明确说明生产应收紧到具体域名（如 `https://api.example.com`）
  - Batch 9 部署阶段统一收紧
  - 不引入 HTML 模板引擎复杂度

## D-FE-006：vite.config.js 补 /docs 和 /openapi.json proxy

- **日期**：2026-07-20
- **背景**：Batch 2 复审指出 dev 模式 API_DOCS_URL 推导为 /docs，但 vite proxy 仅配 /api，dev:web 下点击"API 文档"返回 404。
- **选项**：
  - A. 把 API_DOCS_URL 的 dev fallback 改为 `http://127.0.0.1:8005/docs` 绝对地址
  - B. vite.config.js 补 /docs 和 /openapi.json proxy
  - C. 两者都做
- **选择**：B — vite.config.js 补 proxy
- **理由**：
  - 保持 API_DOCS_URL 推导逻辑统一（同源相对路径）
  - dev 模式走 Vite proxy 避免跨域
  - FastAPI Swagger UI 依赖 /docs 和 /openapi.json 两个路径，一并补全

## D-FE-007：settings 截图体积差异调查结论为非回归

- **日期**：2026-07-20
- **背景**：Batch 2 复审发现 settings-1366x768.png 从基线 60KB 缩小到 34KB（-43%），settings-1920x1080.png 从 77KB 缩小到 38KB（-50%），疑似 UI 回归。
- **调查过程**：
  1. git diff 确认 src/components/ src/hooks/ electron/ backend/ 零改动
  2. 诊断脚本 diagnose-settings.mjs：200ms（loading）与 3000ms（loaded）截图大小几乎一致（34KB）
  3. 验证脚本 verify-settings-loading.mjs：用 Playwright route 拦截 API 请求强制保持 loading 状态，截图仍为 34KB，与 loaded 状态一致
- **结论**：**非 UI 回归**。基线图的 60KB/77KB 是 Batch 1 首次 vite preview 启动时的过渡状态（资源首次加载 + CSS/JS 缓存未热）导致的异常值，无法在 warm 状态下复现。
- **选择**：记录为 F-027 并关闭，不修改任何代码
- **理由**：
  - 业务代码零改动（git diff 证据）
  - loading/loaded 状态截图大小一致（34KB，Playwright route 验证）
  - 基线图异常值无法复现
  - 强行"修复"会引入不必要的改动

## D-FE-008：Tailwind 引用 CSS 变量（D-FE-003 落地实现）

- **日期**：2026-07-20
- **背景**：Batch 3 落地 D-FE-003 决策，将 tailwind.config.js 中的硬编码色值改为引用 src/styles/tokens.css 中定义的 CSS 变量。
- **选择**：`colors: { ide: { bg: 'var(--color-bg-base)' } }` 引用模式
- **理由**：
  - 单一真相：颜色定义只在 tokens.css，tailwind 引用
  - 运行时可配置：CSS 变量可在运行时通过 :root 覆盖
  - 旧类名兼容：业务代码无需立即迁移
  - 不引入两套冲突颜色系统（主计划 §6.2 要求）
- **实现**：
  - tokens.css 定义 `:root { --color-bg-base: #1E1E1E; ... }`
  - tailwind.config.js 引用 `var(--color-bg-base)`
  - index.css `@import './styles/tokens.css'` 在 `@tailwind` 之前
- **后果**：
  - CSS 体积从 20.87KB 增至 32.44KB（+11.57KB，包含 4 个 styles/*.css 全部内容）
  - 截图体积均匀 +6%（CSS 变量引入的统一影响，无回归）
  - gzip CSS 从 4.71KB 到 7.18KB（+2.47KB），在 App 页面 < 50KB CSS 预算内

## D-FE-009：surface.* 色板兼容 3 个 Template Modal

- **日期**：2026-07-20
- **背景**：F-012 发现 PromptTemplateModal/CodeTemplateModal/LadderTemplateModal 使用 `bg-surface`/`border-surface-border`/`bg-surface-alt`/`bg-surface-hover` 类名，但原 tailwind.config.js 未定义 surface 色板。
- **选项**：
  - A. 修改 3 个 Modal 改用 ide.* 类名（需改业务代码）
  - B. 在 tailwind.config.js 添加 surface.* 色板，引用 CSS 变量
  - C. 同时做 A + B
- **选择**：B — 添加 surface.* 兼容
- **理由**：
  - Batch 3 不修改业务代码（仅设计系统层）
  - surface.* 映射到与 ide.* 相同的 CSS 变量（`--color-bg-elevated` 等），视觉一致
  - 后续 Batch 8 重构弹窗时可统一改为 ide.*

## D-FE-010：基础组件用 Compound Component 模式

- **日期**：2026-07-20
- **背景**：Tabs 和 DropdownMenu 需要管理内部状态（active tab / open menu），但又要让调用方控制子项渲染。
- **选项**：
  - A. 单组件 + props 数组（如 `<Tabs items={[...]} />`）
  - B. Compound Component（`<Tabs><Tabs.List><Tabs.Trigger/></Tabs.List></Tabs>`）
  - C. Render Props
- **选择**：B — Compound Component
- **理由**：
  - 父组件拥有状态，子组件通过 context 消费
  - JSX 结构清晰，子项可任意组合
  - 符合 web/rules/patterns.md 的 Compound Components 模式
  - 支持受控/非受控双模式（controlledValue 优先 + onValueChange 回调）
- **实现**：
  - TabsContext + Tabs.List + Tabs.Trigger + Tabs.Content
  - MenuContext + DropdownMenu.Item + DropdownMenu.Separator

## D-FE-011：ConfirmDialog 支持 Esc + 自动聚焦 + 危险按钮具体文案

- **日期**：2026-07-20
- **背景**：主计划 §11.4 要求弹窗支持 Esc 关闭 + 焦点管理 + 危险按钮具体文案。
- **选择**：
  - Esc 关闭：useEffect + keydown 监听 + cleanup
  - 自动聚焦确认按钮：confirmRef.current?.focus() on mount
  - 危险按钮具体文案：confirmLabel prop 由调用方传入（如"确认删除对话"而非"确认"）
  - variant: default/primary/danger，danger 用 btn-danger 样式
- **理由**：
  - 符合主计划 §11.4 弹窗统一要求
  - 符合 web/rules/coding-style.md 可访问性要求
  - 不硬编码文案，由调用方根据上下文传入

## D-FE-012：BottomPanel 挂载状态与折叠状态分离（Batch 4 复审修复）

- **日期**：2026-07-20
- **背景**：Batch 4 复审 F-029 发现 `showBottom` 同时承担"是否挂载 BottomPanel"与"是否折叠内容"两个职责，导致折叠按钮点击后整个面板卸载，Tab 栏消失无法恢复。
- **选项**：
  - A. 保留单状态，去掉折叠按钮（功能倒退）
  - B. BottomPanel 始终挂载，`showBottom` 改为控制 Tab 栏可见性（破坏 Ctrl+\` 持久化语义）
  - C. 分离 `showBottom`（挂载）与 `bottomCollapsed`（折叠内容），两个独立状态
- **选择**：C — 分离两个独立状态
- **理由**：
  - `showBottom`（localStorage 持久化）：控制 BottomPanel 是否挂载，Ctrl+\` 切换
  - `bottomCollapsed`（session 状态）：控制折叠按钮行为，仅折叠内容区，Tab 栏保留
  - 两个状态职责清晰，互不干扰
  - 折叠按钮恢复预期 UX（点一下只折叠内容，再点展开，Tab 栏始终可见）
- **实现**：
  - `const [bottomCollapsed, setBottomCollapsed] = useState(false)`
  - `<BottomPanel collapsed={bottomCollapsed} setCollapsed={setBottomCollapsed} ... />`
  - BottomPanel 接口契约不变，调用方传入独立状态

## D-FE-013：layoutContextValue useMemo + registerModal useCallback（Batch 4 复审修复）

- **日期**：2026-07-20
- **背景**：Batch 4 复审 F-031 发现 `layoutContextValue` 每次渲染新建对象，内联 `registerModal` 函数每次渲染新引用，会导致所有消费 `useLayout()` 的组件强制 re-render。
- **选择**：
  - `registerModal` 用 `useCallback([], [])` 包装（setter 来自 useState，React 18 保证稳定引用）
  - `layoutContextValue` 用 `useMemo` 包装，依赖 `[handleOpenTab, addLog, activeTab, registerModal]`
- **理由**：
  - 避免 Batch 5+ 业务组件接入 useLayout() 时的性能下降
  - 符合 React 性能优化最佳实践
  - 不改变 API 契约，对消费组件透明

## D-FE-014：键盘 useEffect 依赖数组改空 + eslint-disable（Batch 4 复审修复）

- **日期**：2026-07-20
- **背景**：Batch 4 复审 F-032 指出键盘 useEffect 依赖数组 `[setShowSidebar, setShowContext, setShowBottom]` 语义不严谨。React 18 useState dispatch 是稳定引用，等价于空依赖。
- **选择**：依赖数组改 `[]` + `// eslint-disable-next-line react-hooks/exhaustive-deps` + 注释说明
- **理由**：
  - 明确表达"仅 mount 时绑定一次"的语义
  - 注释说明 setter 引用稳定，避免后来者误解
  - eslint-disable 免责声明避免 lint 噪音
  - 行为不变（原本就是等价空依赖）

---

## 待补充
随着各 Batch 推进，继续记录架构决策。
