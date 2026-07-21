import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// F-086/F-022 修复：生产模式收紧 CSP
// - connect-src https: 通配改为 VITE_CSP_CONNECT_SRC 环境变量（生产具体域名）
// - script-src 'unsafe-inline' 移除（Vite 生产构建无内联脚本）
// dev 模式保留宽松 CSP（Vite 热更新需要内联脚本 + localhost 后端）
function cspPlugin() {
  return {
    name: 'csp-meta',
    transformIndexHtml(html, { bundle }) {
      // 仅生产构建（bundle 存在）时收紧
      if (!bundle) return html
      const connectSrc = process.env.VITE_CSP_CONNECT_SRC
      // 若未配置 VITE_CSP_CONNECT_SRC，生产模式警告并保留 https:（向后兼容）
      if (!connectSrc) {
        console.warn('[CSP] VITE_CSP_CONNECT_SRC 未配置，connect-src 保留 https: 通配。生产部署应设置具体域名。')
      }
      const connectSrcValue = connectSrc || 'https:'
      // 生产 CSP：移除 script-src 'unsafe-inline'（Vite 生产构建无内联脚本）
      const prodCsp = `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' ${connectSrcValue}; img-src 'self' data: https:; font-src 'self' data:; frame-src 'none'; object-src 'none'; base-uri 'self';`
      // 替换 meta http-equiv Content-Security-Policy 的 content 属性
      return html.replace(
        /<meta http-equiv="Content-Security-Policy" content="([^"]+)"/,
        (_, _oldContent) => `<meta http-equiv="Content-Security-Policy" content="${prodCsp}"`
      )
    },
  }
}

export default defineConfig({
  plugins: [react(), cspPlugin()],
  base: './',
  test: {
    environment: 'jsdom',
    globals: true,
    // P6 修复：Vitest 默认会匹配 *.spec.js，但 e2e/ 下的 spec 是 Playwright E2E 测试
    // 用 @playwright/test 的 test/expect，不能在 jsdom 环境跑。
    // 显式 include 只跑 src/ 下的 *.test.{js,jsx}
    include: ['src/**/*.{test,spec}.{js,jsx}'],
    exclude: ['e2e/**', 'node_modules/**', 'dist/**', 'playwright-report/**'],
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true,
      },
      // API 文档（FastAPI Swagger UI），dev 模式走 Vite proxy
      '/docs': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true,
      },
      '/openapi.json': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
