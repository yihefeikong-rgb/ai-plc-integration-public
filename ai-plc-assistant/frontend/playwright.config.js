// @ts-check
import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright 配置 — AI PLC Assistant 前端 P6 批次
 *
 * 范围：
 *  - E2E spec 在 e2e/ 目录（5 个关键流程）
 *  - 响应式截图通过 scripts/responsive-screenshot.mjs 单独跑（非 test runner）
 *  - baseURL 默认 http://127.0.0.1:4173（vite preview 端口）
 *  - webServer 自动启 vite preview，复用 dist/ build
 *
 * 运行：
 *   npx playwright test              # 跑全部 E2E
 *   npx playwright test --headed      # 有头模式调试
 *   npx playwright test --grep chat   # 跑名字含 chat 的 spec
 *
 * 不依赖后端：所有 API 通过 page.route() mock。
 * 详见 e2e/fixtures/api-mock.js。
 */

const PORT = process.env.PLAYWRIGHT_PORT || 4173
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${PORT}`

/** @type {import('@playwright/test').PlaywrightTestConfig} */
export default defineConfig({
  testDir: './e2e',
  testMatch: /.*\.spec\.js$/,

  // 单线程串行：避免 localStorage 串污染（不同 spec 共用 origin）
  fullyParallel: false,
  workers: 1,

  // 失败重试：保证 flake 不阻断
  retries: process.env.CI ? 1 : 0,

  // 超时：10s/test（首启 preview 慢一些）
  timeout: 30_000,
  expect: { timeout: 5_000 },

  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],

  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',

    // jsdom 无 console.error，但浏览器有；失败时打印 console error 帮助诊断
    // 不强制 fail on console.error：dev preview 可能有 React 18 act 警告
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  webServer: {
    // E2E 用 VITE_API_BASE=/api 让 build 同源（page.route 拦截 + 避开生产 CSP 跨域阻断）
    command: 'cross-env VITE_API_BASE=/api npm run build:web && cross-env VITE_API_BASE=/api npm run preview:web -- --port ' + PORT + ' --strictPort',
    url: BASE_URL,
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
    cwd: '.',
  },
})
