/**
 * Batch 2 验证截图脚本
 *
 * 验证 Batch 2 双模式改造后 UI 与 Batch 1 基线一致。
 * 截 4 个核心页面 x 2 尺寸 = 8 张，存到 screenshots/batch2-verify/。
 */

import { chromium } from '@playwright/test'
import { mkdirSync } from 'fs'
import { resolve } from 'path'

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:4173'
const OUT_DIR = resolve('../../docs/frontend/screenshots/batch2-verify')

const VIEWPORTS = [
  { width: 1366, height: 768, suffix: '1366x768' },
  { width: 1920, height: 1080, suffix: '1920x1080' },
]

const PAGES = [
  { name: 'dashboard', action: async (page) => { await page.goto(BASE_URL + '/'); await page.waitForTimeout(800); } },
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
    name: 'settings',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      await page.locator('aside button:has-text("设置")').first().click()
      await page.waitForTimeout(300)
      await page.locator('aside button:has-text("模型配置")').first().click()
      await page.waitForTimeout(1000)
    },
  },
  {
    name: 'ladder',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      await page.locator('aside button:has-text("梯形图生成")').first().click()
      await page.waitForTimeout(500)
    },
  },
]

async function run() {
  mkdirSync(OUT_DIR, { recursive: true })
  const browser = await chromium.launch({ headless: true })

  let succeeded = 0
  let failed = 0

  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 1,
    })
    const page = await context.newPage()

    for (const p of PAGES) {
      const filename = `${p.name}-${vp.suffix}.png`
      const outPath = resolve(OUT_DIR, filename)
      try {
        await p.action(page)
        await page.waitForTimeout(300)
        await page.screenshot({ path: outPath, fullPage: false })
        console.log(`[OK] ${filename}`)
        succeeded++
      } catch (err) {
        console.log(`[FAIL] ${filename}: ${err.message}`)
        failed++
      }
    }
    await context.close()
  }

  await browser.close()
  console.log(`\n成功: ${succeeded}, 失败: ${failed}`)
  process.exit(failed > 0 ? 1 : 0)
}

run().catch((err) => {
  console.error('截图脚本异常:', err)
  process.exit(1)
})
