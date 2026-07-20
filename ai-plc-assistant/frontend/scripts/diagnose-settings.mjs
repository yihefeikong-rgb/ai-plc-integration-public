/**
 * 诊断 settings 截图差异：对比 Batch 1 基线与 Batch 2 verify 的 DOM 内容。
 *
 * 在同一次运行中：
 * 1. 截图 200ms（loading 状态）和 3000ms（loaded 状态）两个时刻
 * 2. 输出每个时刻的 DOM 文本长度 + 截图文件大小
 * 3. 判断差异是来自 UI 状态还是 PNG 压缩
 */

import { chromium } from '@playwright/test'
import { statSync, writeFileSync } from 'fs'
import { resolve } from 'path'

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:4173'
const OUT_DIR = resolve('../../docs/frontend/screenshots/batch2-diagnose')

async function run() {
  const browser = await chromium.launch({ headless: true })

  for (const vp of [{ width: 1366, height: 768, suffix: '1366x768' }, { width: 1920, height: 1080, suffix: '1920x1080' }]) {
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 1,
    })
    const page = await context.newPage()

    await page.goto(BASE_URL + '/')
    await page.waitForTimeout(500)
    await page.locator('aside button:has-text("设置")').first().click()
    await page.waitForTimeout(300)
    await page.locator('aside button:has-text("模型配置")').first().click()

    // 截图 1：200ms（可能 loading 中）
    await page.waitForTimeout(200)
    const path1 = resolve(OUT_DIR, `settings-${vp.suffix}-200ms.png`)
    await page.screenshot({ path: path1, fullPage: false })
    const html1 = await page.content()
    const size1 = statSync(path1).size

    // 截图 2：再等 2800ms（总 3000ms，应该 loaded）
    await page.waitForTimeout(2800)
    const path2 = resolve(OUT_DIR, `settings-${vp.suffix}-3000ms.png`)
    await page.screenshot({ path: path2, fullPage: false })
    const html2 = await page.content()
    const size2 = statSync(path2).size

    // 输出 DOM 文本（去掉 HTML 标签）
    const text1 = html1.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
    const text2 = html2.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()

    writeFileSync(resolve(OUT_DIR, `settings-${vp.suffix}-200ms.txt`), text1)
    writeFileSync(resolve(OUT_DIR, `settings-${vp.suffix}-3000ms.txt`), text2)

    console.log(`\n=== ${vp.suffix} ===`)
    console.log(`200ms:  size=${size1} htmlLen=${html1.length} textLen=${text1.length}`)
    console.log(`3000ms: size=${size2} htmlLen=${html2.length} textLen=${text2.length}`)
    console.log(`text 200ms: ${text1.slice(0, 300)}`)
    console.log(`text 3000ms: ${text2.slice(0, 300)}`)

    await context.close()
  }

  await browser.close()
}

run().catch((err) => {
  console.error('诊断脚本异常:', err)
  process.exit(1)
})
