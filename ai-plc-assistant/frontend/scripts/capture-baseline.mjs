/**
 * Batch 1 基线截图脚本
 *
 * 使用 Playwright Chromium 截图当前前端主要页面。
 * 14 个页面 x 2 尺寸（1366x768 + 1920x1080）。
 *
 * 运行：node scripts/capture-baseline.mjs
 * 前置：npx vite preview --port 4173
 */

import { chromium } from '@playwright/test'
import { mkdirSync } from 'fs'
import { resolve } from 'path'

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:4173'
const OUT_DIR = resolve('../../docs/frontend/screenshots/before')

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
      // 点击 Toolbar AI 菜单
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
      await page.locator('aside button:has-text("梯形图生成")').first().click()
      await page.waitForTimeout(500)
    },
  },
  {
    name: 'program-parser',
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
      await page.locator('aside button:has-text("IO表生成")').first().click()
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
    name: 'fault-diagnosis',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      await page.locator('aside button:has-text("故障诊断")').first().click()
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
  {
    name: 'settings',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      // 展开"设置" Section（默认折叠）
      const settingsHeader = page.locator('aside button:has-text("设置")').first()
      await settingsHeader.click()
      await page.waitForTimeout(300)
      // 子项"模型配置"
      await page.locator('aside button:has-text("模型配置")').first().click()
      await page.waitForTimeout(1000)
    },
  },
  {
    name: 'prompt-template-modal',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      // 展开"知识库" Section（默认折叠）
      const kbHeader = page.locator('aside button:has-text("知识库")').first()
      await kbHeader.click()
      await page.waitForTimeout(300)
      await page.locator('aside button:has-text("提示词模板")').first().click()
      await page.waitForTimeout(1000)
    },
  },
  {
    name: 'code-template-modal',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      const kbHeader = page.locator('aside button:has-text("知识库")').first()
      await kbHeader.click()
      await page.waitForTimeout(300)
      await page.locator('aside button:has-text("SCL代码模板")').first().click()
      await page.waitForTimeout(1000)
    },
  },
  {
    name: 'ladder-template-modal',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      const kbHeader = page.locator('aside button:has-text("知识库")').first()
      await kbHeader.click()
      await page.waitForTimeout(300)
      await page.locator('aside button:has-text("梯形图模板")').first().click()
      await page.waitForTimeout(1000)
    },
  },
  {
    name: 'create-project-dialog',
    action: async (page) => {
      await page.goto(BASE_URL + '/')
      await page.waitForTimeout(500)
      await page.locator('aside button:has-text("新建项目")').first().click()
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

    // 捕获 console 错误
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

  console.log('\n========== 截图完成 ==========')
  console.log(`成功: ${succeeded}`)
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
