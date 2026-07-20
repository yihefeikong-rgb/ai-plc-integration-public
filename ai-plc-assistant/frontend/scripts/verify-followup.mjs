// 收尾批次截图验证 — D-1~D-4 + A-1~A-3 + B-1~B-4
// 截图关键页面到 docs/frontend/screenshots/followup-verify/
import { chromium } from 'playwright'
import { mkdirSync } from 'fs'
import { dirname } from 'path'

const OUT_DIR = 'docs/frontend/screenshots/followup-verify'
const BASE = 'http://localhost:4174'

const PAGES = [
  { id: 'dashboard', path: '/', action: async (page) => {
    // 等待 Dashboard 加载
    await page.waitForTimeout(800)
  }},
  { id: 'chat', path: '/', action: async (page) => {
    // 点击侧栏 AI 助手
    await page.waitForTimeout(500)
    const aiItem = page.locator('text=AI 助手').first()
    if (await aiItem.isVisible().catch(() => false)) await aiItem.click()
    await page.waitForTimeout(500)
  }},
  { id: 'ladder', path: '/', action: async (page) => {
    await page.waitForTimeout(500)
    const ladderItem = page.locator('text=梯形图生成').first()
    if (await ladderItem.isVisible().catch(() => false)) await ladderItem.click()
    await page.waitForTimeout(500)
  }},
  { id: 'orchestrator', path: '/', action: async (page) => {
    await page.waitForTimeout(500)
    const orchItem = page.locator('text=编排管理').first()
    if (await orchItem.isVisible().catch(() => false)) await orchItem.click()
    await page.waitForTimeout(500)
  }},
]

const SIZES = [
  { w: 1366, h: 768 },
  { w: 1920, h: 1080 },
]

async function main() {
  mkdirSync(OUT_DIR, { recursive: true })
  const browser = await chromium.launch()
  const context = await browser.newContext()

  for (const page of PAGES) {
    for (const size of SIZES) {
      const p = await context.newPage()
      await p.setViewportSize({ width: size.w, height: size.h })
      await p.goto(BASE + page.path, { waitUntil: 'networkidle' })
      await page.action(p)
      const out = `${OUT_DIR}/${page.id}-${size.w}x${size.h}.png`
      mkdirSync(dirname(out), { recursive: true })
      await p.screenshot({ path: out, fullPage: false })
      console.log(`saved: ${out}`)
      await p.close()
    }
  }

  await browser.close()
  console.log('followup verification screenshots done')
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
