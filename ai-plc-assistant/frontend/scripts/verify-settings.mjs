/**
 * 重新截图 settings 页，验证与 Batch 1 基线一致。
 *
 * Batch 2 复审指出 settings 截图体积缩小 ~45-50%，
 * 此脚本用与基线完全相同的等待时间 (1000ms) 与导航路径
 * 重截 settings-1366x768.png / settings-1920x1080.png，
 * 与基线对比文件大小。
 */

import { chromium } from '@playwright/test'
import { mkdirSync, statSync } from 'fs'
import { resolve } from 'path'

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:4173'
const OUT_DIR = resolve('../../docs/frontend/screenshots/batch2-verify')
const BASELINE_DIR = resolve('../../docs/frontend/screenshots/before')

const VIEWPORTS = [
  { width: 1366, height: 768, suffix: '1366x768' },
  { width: 1920, height: 1080, suffix: '1920x1080' },
]

async function run() {
  mkdirSync(OUT_DIR, { recursive: true })
  const browser = await chromium.launch({ headless: true })

  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 1,
    })
    const page = await context.newPage()

    // 与基线脚本完全一致的导航路径
    await page.goto(BASE_URL + '/')
    await page.waitForTimeout(500)
    // 展开"设置" Section（默认折叠）
    await page.locator('aside button:has-text("设置")').first().click()
    await page.waitForTimeout(300)
    await page.locator('aside button:has-text("模型配置")').first().click()
    // 与基线脚本完全一致的等待时间
    await page.waitForTimeout(1000)

    const filename = `settings-${vp.suffix}.png`
    const outPath = resolve(OUT_DIR, filename)
    await page.screenshot({ path: outPath, fullPage: false })

    const baselinePath = resolve(BASELINE_DIR, filename)
    const newSize = statSync(outPath).size
    const baselineSize = statSync(baselinePath).size
    const ratio = ((newSize / baselineSize) * 100).toFixed(1)
    const delta = newSize - baselineSize

    console.log(`${filename}: baseline=${baselineSize} new=${newSize} ratio=${ratio}% delta=${delta > 0 ? '+' : ''}${delta}`)
    await context.close()
  }

  await browser.close()
}

run().catch((err) => {
  console.error('截图脚本异常:', err)
  process.exit(1)
})
