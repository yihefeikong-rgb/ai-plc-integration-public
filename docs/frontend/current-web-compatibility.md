# 当前 Web 兼容性评估

> 生成日期：2026-07-20
> Batch：1
> 范围：`ai-plc-assistant/frontend/` Web 浏览器部署可行性

---

## 1. 总体结论

当前前端 **Web 兼容性良好**，主要障碍是 API_BASE 硬编码和 CSP 限制。Electron 专属调用极少（仅 preload.js 暴露 `electronAPI.getAppVersion()`，业务代码未使用）。

## 2. 已具备 Web 兼容性的功能

| 功能 | 实现方式 | 兼容性 |
|------|---------|--------|
| 文件上传（项目导入/知识库导入） | `<input type="file">` + FormData | ✅ 浏览器原生 |
| 文件下载（导出 SCL/XML/CSV/HMI） | Blob + URL.createObjectURL + `<a download>` | ✅ 浏览器原生 |
| SSE 流式输出 | fetch + ReadableStream + TextDecoder | ✅ 浏览器原生 |
| 中断生成 | AbortController signal | ✅ 浏览器原生（streamChat 已支持 signal 参数） |
| 本地 Token 请求头 | `X-Local-Api-Token` header | ✅ 浏览器原生 |
| localStorage 历史记录 | `localStorage.getItem/setItem` | ✅ 浏览器原生 |
| Markdown 渲染 | `react-markdown` 库 | ✅ 浏览器兼容 |
| 图标 | `lucide-react` | ✅ 浏览器兼容 |
| CSS 滚动条样式 | `::-webkit-scrollbar` | ⚠️ Chrome/Edge/Safari 支持，Firefox 不支持（fallback 默认样式） |
| CSV/XML/SCL/HMI 导出 | 后端返回内容，前端 Blob 下载 | ✅ 浏览器原生 |
| 知识库文档管理 | listDocuments/uploadDocument/deleteDocument | ✅ 浏览器原生 |
| 工程搜索 | searchProjects GET | ✅ 浏览器原生 |

## 3. Web 兼容性问题

### 3.1 API_BASE 硬编码生产地址
**位置**：`src/api.js:4`
```js
export const API_BASE = import.meta.env.DEV ? '/api' : 'http://127.0.0.1:8005/api'
```
**问题**：
- 生产模式硬编码 `http://127.0.0.1:8005/api`
- Web 部署到非本机后端时无法配置
- Web 部署到 HTTPS 时混合内容（HTTPS 页面调用 HTTP API 被浏览器拒绝）

**修复方案**（Batch 2）：
```js
export const API_BASE = import.meta.env.VITE_API_BASE || '/api'
```
配合 `.env.production`：
```
VITE_API_BASE=https://api.example.com/api
```

### 3.2 CSP 限制
**位置**：`index.html:6`
```html
<meta http-equiv="Content-Security-Policy" content="
  default-src 'self';
  script-src 'self' 'unsafe-inline';
  style-src 'self' 'unsafe-inline';
  connect-src 'self' http://localhost:*;" />
```
**问题**：
- `connect-src 'self' http://localhost:*` 限制 fetch/WebSocket 到 self + localhost
- Web 部署后调用远程 API 被拦截
- `script-src 'unsafe-inline'` 允许内联脚本，安全性较低

**修复方案**（Batch 2/3）：
- Web 模式：CSP 改为 `connect-src 'self' https://api.example.com;`
- Electron 模式：CSP 保持 `connect-src 'self' http://localhost:*;`
- 用 nonce-based CSP 替代 `'unsafe-inline'`

### 3.3 window.open API 文档
**位置**：`src/App.jsx:82`
```js
case 'help:api-docs': window.open('http://127.0.0.1:8005/docs', '_blank'); break
```
**问题**：
- Web 部署后 `127.0.0.1:8005` 不可达
- 应改为相对路径 `/docs` 或环境变量

**修复方案**（Batch 2）：
```js
case 'help:api-docs': window.open(`${API_BASE.replace('/api','')}/docs`, '_blank'); break
```

### 3.4 Vite base 路径
**位置**：`vite.config.js:6`
```js
base: './'
```
**当前**：相对路径，子路径部署友好。
**Web 兼容性**：✅ 已就绪。

### 3.5 Vite proxy 配置
**位置**：`vite.config.js:13-19`
```js
server: {
  port: 5173,
  strictPort: true,
  proxy: {
    '/api': { target: 'http://127.0.0.1:8005', changeOrigin: true },
  },
}
```
**当前**：dev 模式走 Vite proxy。
**Web 兼容性**：✅ dev 模式就绪。
**生产模式**：需要后端配置反向代理或 CORS。

### 3.6 Electron 专属调用
**位置**：`electron/preload.js`
```js
contextBridge.exposeInMainWorld('electronAPI', {
  getAppVersion: () => '0.1.0',
})
```
**当前**：仅暴露 `getAppVersion`，业务代码未调用 `window.electronAPI`。
**Web 兼容性**：✅ 业务代码不依赖 Electron API。
**建议**：建立 `src/platform/runtime.js` 统一判断：
```js
export const isElectron = () => typeof window !== 'undefined' && !!window.electronAPI
export const isWeb = () => !isElectron()
export const getRuntimeMode = () => isElectron() ? 'electron' : 'web'
```

### 3.7 静态部署路径
**当前**：`base: './'` + `dist/index.html` 使用相对路径。
**Web 部署**：
- Nginx/Apache：直接拷贝 `dist/` 到 web root
- 子路径部署：`base: './'` 自动适配
- CDN：可配合 `VITE_API_BASE` 环境变量

**兼容性**：✅ 就绪。

### 3.8 浏览器刷新
**当前**：Tab 路由用 `useTabs` 内部状态，无 URL 路由。
**问题**：
- 刷新后 Tab 状态丢失（回到 welcome）
- 浏览器后退/前进按钮无效
- 无法分享 URL 定位到特定 Tab

**修复方案**（Batch 4 或 9）：
- 用 `history.pushState` 同步 `activeTab` 到 URL hash（如 `#/chat`）
- 或引入 `react-router` 但增加 bundle 体积
- 主计划未明确要求 URL 路由，可保留状态路由 + localStorage 持久化 Tab

### 3.9 历史记录 localStorage
**当前**：`useWorkbenchHistory` 用 `wb_history_${key}` 存储。
**Web 兼容性**：✅ 浏览器原生 localStorage。
**配额**：通常 5-10MB，maxItems=20 足够。

### 3.10 SSE 流式
**当前**：`streamChat` 用 `fetch + ReadableStream + TextDecoder`。
**Web 兼容性**：✅ 浏览器原生。
**问题**：
- HTTP/1.1 同源限制 6 个并发连接
- 长连接可能被代理超时（Nginx 默认 60s）
- 需要后端设置 `Cache-Control: no-cache` 和 `X-Accel-Buffering: no`

**建议**：Web 部署时反向代理配置：
```nginx
location /api/chat/stream {
  proxy_pass http://backend;
  proxy_buffering off;
  proxy_read_timeout 3600s;
}
```

## 4. 跨域 CORS

### 4.1 当前 dev 模式
- 前端 `localhost:5173` → Vite proxy → 后端 `127.0.0.1:8005`
- 同源：✅ 无 CORS 问题

### 4.2 生产模式 Web
- 前端 `https://app.example.com` → 后端 `https://api.example.com`
- 跨域：❌ 需要后端配置 CORS

**后端需配置**（不在本任务范围，记录到 findings.md）：
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.example.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 4.3 生产模式 Electron
- 前端 `file://` 或 `app://` → 后端 `http://127.0.0.1:8005`
- 跨域：❌ 需要后端允许 `*` 或 Electron origin

## 5. 兼容性验证清单（Batch 2 需验证）

主计划 Batch 2 要求验证：

| 项 | 当前状态 | Batch 2 验证 |
|----|---------|------|
| 文件上传 | ✅ 浏览器原生 | 验证 Web 模式上传 |
| 工程导入 | ✅ FormData | 验证 Web 模式导入 |
| 知识库导入 | ✅ FormData | 验证 Web 模式导入 |
| Blob 下载 | ✅ 浏览器原生 | 验证 Web 模式导出 |
| CSV/XML/SCL/HMI 导出 | ✅ Blob | 验证 4 种格式 |
| window.open | ❌ 硬编码 localhost | 改为相对路径 |
| API 文档 | ❌ 硬编码 localhost | 改为相对路径 |
| SSE 流式输出 | ✅ fetch + ReadableStream | 验证 Web 模式 SSE |
| 中断生成 | ✅ AbortController | 验证 Web 模式中断 |
| 本地 Token 请求头 | ✅ header | 验证 Web 模式 Token |
| 浏览器刷新 | ⚠️ Tab 状态丢失 | 评估是否需 URL 路由 |
| 静态部署路径 | ✅ base: './' | 验证 Nginx 子路径部署 |

## 6. 已识别的后端依赖（不在前端修改范围）

记录到 findings.md，不修改后端：

1. **CORS 配置**：Web 部署需后端允许前端域名
2. **SSE 反向代理超时**：Nginx 需 `proxy_buffering off`
3. **API Key 返回脱敏**：后端 `/settings` 返回应脱敏 API Key
4. **API 文档 URL**：后端 `/docs` 路径需在 Web 模式可达

## 7. 建议改造步骤（Batch 2）

### 7.1 修改文件
- `src/api.js`：`API_BASE` 改为环境变量优先
- `src/App.jsx`：`window.open` 改为相对路径
- `vite.config.js`：保留 proxy 不变
- `index.html`：CSP 改为支持环境变量配置

### 7.2 新增文件
- `src/platform/runtime.js`：`isElectron/isWeb/getRuntimeMode`
- `.env.example`：示例环境变量
- `.env.development`：开发环境（`VITE_API_BASE=/api`）
- `.env.production.example`：生产环境示例（`VITE_API_BASE=https://api.example.com/api`）

### 7.3 package.json scripts
```json
{
  "scripts": {
    "dev:web": "vite --host 0.0.0.0",
    "dev:renderer": "vite",
    "dev:electron": "concurrently \"npm run dev:renderer\" \"wait-on http://localhost:5173 && electron .\"",
    "dev": "npm run dev:electron",
    "build:web": "vite build",
    "preview:web": "vite preview --host 0.0.0.0",
    "build:electron": "vite build && electron-builder",
    "pack:electron": "vite build && electron-builder --dir",
    "test": "vitest run"
  }
}
```

### 7.4 验证
- `npm run dev:web` 启动 → 浏览器访问 `http://localhost:5173`
- `npm run build:web` → `dist/` 部署到 Nginx
- `npm run preview:web` → 验证生产构建
- `npm run dev:electron` → Electron 桌面模式
- `npm run build:electron` → 桌面安装包

## 8. 兼容性评分

| 维度 | 评分 | 说明 |
|------|------|------|
| API 调用 | 6/10 | 硬编码需改 |
| 文件上传下载 | 10/10 | 浏览器原生 |
| SSE | 9/10 | 浏览器原生，需代理配置 |
| Token 处理 | 7/10 | 构建时硬编码 |
| CSP | 5/10 | 需环境化 |
| Electron 专属 | 10/10 | 业务代码无依赖 |
| 静态部署 | 9/10 | base: './' 就绪 |
| 浏览器刷新 | 6/10 | Tab 状态丢失 |
| **综合** | **7.5/10** | 主要改 API_BASE + CSP + window.open |
