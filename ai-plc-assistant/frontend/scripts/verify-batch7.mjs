/**
 * Batch 7 验证截图
 *
 * F-007 修复（5 个工具页面 model_id 用 selectedModel）+ ToolStatusBar 组件提取。
 * 截 5 个工具页面 x 1 尺寸 = 5 张，确认 UI 无回归。
 */
import { chromium } from '@playwright/test'
import { mkdirSync, statSync } from 'fs'
import { resolve } from 'path'

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:4173'
const OUT_DIR = resolve('../../docs/frontend/screenshots/batch7-verify')

const PAGES = [
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
    name: 'parse',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      await page.locator('aside button:has-text("程序解析")').first().click()
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
    name: 'variables',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      await page.locator('aside button:has-text("变量分析")').first().click()
      await page.waitForTimeout(500)
    },
  },
  {
    name: 'diagnose',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      await page.locator('aside button:has-text("故障诊断")').first().click()
      await page.waitForTimeout(500)
    },
  },
]

async function run() {
  mkdirSync(OUT_DIR, { recursive: true })
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 })
  const page = await ctx.newPage()
  let ok = 0, fail = 0
  for (const p of PAGES) {
    const fn = `${p.name}-1366x768.png`
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
  await browser.close()
  console.log(`\n成功: ${ok}, 失败: ${fail}`)
  process.exit(fail > 0 ? 1 : 0)
}

run().catch((err) => { console.error('截图异常:', err); process.exit(1) })
