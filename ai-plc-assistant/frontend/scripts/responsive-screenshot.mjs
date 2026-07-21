/**
 * P6 响应式截图脚本 — 4 尺寸 × 关键页面
 *
 * 用法：
 *   node scripts/responsive-screenshot.mjs
 *   BASE_URL=http://127.0.0.1:4173 node scripts/responsive-screenshot.mjs
 *
 * 前置：vite preview --port 4173 --strictPort
 *   （或 playwright.config.js 的 webServer 已自动启动）
 *
 * 输出：docs/frontend/screenshots/responsive/<page>-<viewport>.png
 *
 * 4 尺寸：1366 / 1600 / 1920 / 2560
 * 8 关键页面：dashboard / chat / ladder / io-table / fault-diagnosis /
 *            variable-analyzer / orchestrator / robot
 *
 * 截图前给页面 800ms 稳定时间，避免动画卡顿。
 */

import { chromium } from '@playwright/test'
import { mkdirSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:4173'
// 路径：__dirname 是 ai-plc-assistant/frontend/scripts/，../../../ 到仓库根 docs/
const OUT_DIR = resolve(__dirname, '../../../docs/frontend/screenshots/responsive')

const VIEWPORTS = [
  { width: 1366, height: 768, suffix: '1366' },   // 笔记本常见
  { width: 1600, height: 900, suffix: '1600' },  // 桌面 16:9
  { width: 1920, height: 1080, suffix: '1920' },  // FHD
  { width: 2560, height: 1440, suffix: '2560' },  // QHD 2K
]

const PAGES = [
  {
    name: 'dashboard',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(800)
    },
  },
  {
    name: 'chat',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      // 通过 TopBar "AI" 菜单 → 新建对话（参考 capture-baseline.mjs）
      await page.locator('header button:has-text("AI")').first().click()
      await page.waitForTimeout(200)
      await page.locator('div[class*="absolute"] button:has-text("新建对话")').first().click()
      await page.waitForTimeout(800)
    },
  },
  {
    name: 'ladder',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      await page.locator('aside button:has-text("梯形图")').first().click()
      await page.waitForTimeout(500)
    },
  },
  {
    name: 'io-table',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      await page.locator('aside button:has-text("IO 表")').first().click()
      await page.waitForTimeout(500)
    },
  },
  {
    name: 'fault-diagnosis',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      await page.locator('aside button:has-text("故障诊断")').first().click()
      await page.waitForTimeout(500)
    },
  },
  {
    name: 'variable-analyzer',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      await page.locator('aside button:has-text("变量分析")').first().click()
      await page.waitForTimeout(500)
    },
  },
  {
    name: 'orchestrator',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      await page.locator('aside button:has-text("编排管理")').first().click()
      await page.waitForTimeout(1500)
    },
  },
  {
    name: 'robot',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      await page.locator('aside button:has-text("机器人")').first().click()
      await page.waitForTimeout(500)
    },
  },
]

async function run() {
  mkdirSync(OUT_DIR, { recursive: true })
  const browser = await chromium.launch({ headless: true })

  let succeeded = 0
  let failed = 0
  const failures = []

  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 1,
    })
    const page = await context.newPage()

    const consoleErrors = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text())
    })
    page.on('pageerror', (err) => {
      consoleErrors.push(`pageerror: ${err.message}`)
    })

    for (const p of PAGES) {
      const filename = `${p.name}-${vp.suffix}.png`
      const outPath = resolve(OUT_DIR, filename)
      try {
        consoleErrors.length = 0
        await p.action(page)
        await page.waitForTimeout(300)
        await page.screenshot({ path: outPath, fullPage: false })
        if (consoleErrors.length > 0) {
          console.log(`[WARN] ${filename}: ${consoleErrors.length} console errors (expected due to no backend)`)
        }
        console.log(`[OK] ${filename}`)
        succeeded++
      } catch (err) {
        console.log(`[FAIL] ${filename}: ${err.message}`)
        failures.push({ filename, error: err.message })
        failed++
      }
    }

    await context.close()
  }

  await browser.close()

  console.log('\n========== 响应式截图完成 ==========')
  console.log(`成功: ${succeeded}/${succeeded + failed}`)
  console.log(`失败: ${failed}`)
  if (failures.length > 0) {
    console.log('\n失败详情:')
    for (const f of failures) console.log(`  ${f.filename}: ${f.error}`)
  }
  process.exit(failed > 0 ? 1 : 0)
}

run().catch((err) => {
  console.error('截图脚本异常:', err)
  process.exit(1)
})
