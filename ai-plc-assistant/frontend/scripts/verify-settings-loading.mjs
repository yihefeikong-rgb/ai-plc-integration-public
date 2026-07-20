/**
 * 精确验证：用 Playwright route 拦截 API 请求，对比 loading 与 loaded 两态截图大小。
 *
 * 假设：基线图 60KB 是 loading 状态（getSettings/getProviders 请求 pending），
 *      verify 图 34KB 是 loaded 状态（请求快速失败，显示完整表单）。
 *
 * 验证：
 * 1. 拦截 /api/settings 和 /api/settings/providers，让它们永不返回（模拟基线时的慢失败）
 * 2. 截图 settings 页 → 应该是 loading 状态 → 期望 ~60KB
 * 3. 另一次运行不拦截，让请求快速失败 → 应该是 loaded 状态 → 期望 ~34KB
 */

import { chromium } from '@playwright/test'
import { statSync } from 'fs'
import { resolve } from 'path'

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:4173'
const OUT_DIR = resolve('../../docs/frontend/screenshots/batch2-loading-test')

async function run() {
  const browser = await chromium.launch({ headless: true })

  for (const scenario of ['loading', 'loaded']) {
    for (const vp of [{ width: 1366, height: 768, suffix: '1366x768' }, { width: 1920, height: 1080, suffix: '1920x1080' }]) {
      const context = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        deviceScaleFactor: 1,
      })
      const page = await context.newPage()

      if (scenario === 'loading') {
        // 拦截 API 请求，永不返回（模拟基线时的慢失败 / pending）
        await page.route('**/api/settings', (route) => {
          // 不调用 route.fulfill / route.abort，让请求永久 pending
        })
        await page.route('**/api/settings/providers', (route) => {
          // 不调用 route.fulfill / route.abort，让请求永久 pending
        })
      }

      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      await page.locator('aside button:has-text("设置")').first().click()
      await page.waitForTimeout(300)
      await page.locator('aside button:has-text("模型配置")').first().click()
      await page.waitForTimeout(1000)

      const filename = `settings-${scenario}-${vp.suffix}.png`
      const path = resolve(OUT_DIR, filename)
      await page.screenshot({ path, fullPage: false })
      const size = statSync(path).size

      console.log(`${filename}: size=${size}`)
      await context.close()
    }
  }

  await browser.close()
}

run().catch((err) => {
  console.error('验证脚本异常:', err)
  process.exit(1)
})
