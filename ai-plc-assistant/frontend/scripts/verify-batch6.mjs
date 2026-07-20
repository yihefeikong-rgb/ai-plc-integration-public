/**
 * Batch 6 验证截图
 *
 * ChatArea 重构为工程 AI 工作区 + 13 种消息类型框架 + 输入区扩展 + 停止生成 + F-026 修复。
 * 截 4 个核心页面 x 2 尺寸 = 8 张，重点关注 chat 页面。
 */
import { chromium } from '@playwright/test'
import { mkdirSync, statSync } from 'fs'
import { resolve } from 'path'

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:4173'
const OUT_DIR = resolve('../../docs/frontend/screenshots/batch6-verify')

const VIEWPORTS = [
  { width: 1366, height: 768, suffix: '1366x768' },
  { width: 1920, height: 1080, suffix: '1920x1080' },
]

const PAGES = [
  { name: 'dashboard', action: async (page) => { await page.goto(BASE_URL + '/'); await page.waitForTimeout(1000); } },
  {
    name: 'chat',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      await page.locator('aside button:has-text("AI 助手")').first().click()
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
