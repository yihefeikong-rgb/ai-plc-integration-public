/**
 * Batch 4 验证截图
 *
 * 应用外壳重构后，UI 将与 Batch 3 有明显差异（顶部状态栏 + 4 分组导航 + 7 Tab 底部）。
 * 截 4 个核心页面 x 2 尺寸 = 8 张，仅作为 Batch 4 后基线，不与 Batch 3 对比。
 */
import { chromium } from '@playwright/test'
import { mkdirSync, statSync } from 'fs'
import { resolve } from 'path'

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:4173'
const OUT_DIR = resolve('../../docs/frontend/screenshots/batch4-verify')

const VIEWPORTS = [
  { width: 1366, height: 768, suffix: '1366x768' },
  { width: 1920, height: 1080, suffix: '1920x1080' },
]

const PAGES = [
  { name: 'dashboard', action: async (page) => { await page.goto(BASE_URL + '/'); await page.waitForTimeout(800); } },
  {
    name: 'chat',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      // 工作区分组默认展开，点击 AI 助手
      await page.locator('aside button:has-text("AI 助手")').first().click()
      await page.waitForTimeout(500)
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
    name: 'orchestrator',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      await page.locator('aside button:has-text("编排管理")').first().click()
      await page.waitForTimeout(1500)
    },
  },
]

async function run() {
  mkdirSync(OUT_DIR, { recursive: true })
  const browser = await chromium.launch({ headless: true })
  let ok = 0, fail = 0
  for (const vp of VIEWPORTS) {
    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 1 })
    const page = await ctx.newPage()
    for (const p of PAGES) {
      const fn = `${p.name}-${vp.suffix}.png`
      try {
        await p.action(page)
        await page.waitForTimeout(300)
        await page.screenshot({ path: resolve(OUT_DIR, fn), fullPage: false })
        const sz = statSync(resolve(OUT_DIR, fn)).size
        console.log(`[OK] ${fn}: ${sz} bytes`)
        ok++
      } catch (err) {
        console.log(`[FAIL] ${fn}: ${err.message}`)
        fail++
      }
    }
    await ctx.close()
  }
  await browser.close()
  console.log(`\n成功: ${ok}, 失败: ${fail}`)
  process.exit(fail > 0 ? 1 : 0)
}

run().catch((err) => { console.error('截图异常:', err); process.exit(1) })
