/**
 * E2E-2: Sidebar 工作区切换 — 验证点击不同工具页后 sidebar active 状态切换 + 主面板渲染
 *
 * 覆盖路径：sidebar → 工作区按钮 → active class 切换 + 主面板内容切换
 *
 * 验证策略：
 *  1. sidebar 按钮点击后，active class 切换（bg-accent/10）
 *  2. 主面板渲染对应工具页标题（用更精确 selector 避开 TopBar 内 .flex-1）
 */
import { test, expect } from '@playwright/test'
import { mockApi } from './fixtures/api-mock.js'

// 主面板 selector：AppShell 渲染的 `<div className="flex-1 flex overflow-hidden">` 是主容器
// 但 TopBar 内也有 .flex-1 元素，需用更精确组合
const MAIN_PANEL = 'div.flex-1.flex.overflow-hidden > div.flex-1'

test.describe('Sidebar 工作区切换', () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page)
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)
  })

  test('点击梯形图 → sidebar active + 主面板渲染', async ({ page }) => {
    const ladderBtn = page.locator('aside button:has-text("梯形图")').first()
    await ladderBtn.click()
    await page.waitForTimeout(500)

    // sidebar active class 切换
    await expect(ladderBtn).toHaveClass(/bg-accent/)

    // 主面板出现"梯形图"字样（标题栏或工具栏）
    const mainContent = page.locator(MAIN_PANEL).first()
    await expect(mainContent).toContainText('梯形图', { timeout: 3000 })

    await page.screenshot({ path: 'e2e/screenshots/tab-ladder.png' })
  })

  test('点击 IO 表 → sidebar active + 主面板渲染', async ({ page }) => {
    const ioBtn = page.locator('aside button:has-text("IO 表")').first()
    await ioBtn.click()
    await page.waitForTimeout(500)

    await expect(ioBtn).toHaveClass(/bg-accent/)

    const mainContent = page.locator(MAIN_PANEL).first()
    await expect(mainContent).toContainText('IO', { timeout: 3000 })

    await page.screenshot({ path: 'e2e/screenshots/tab-io-table.png' })
  })

  test('点击故障诊断 → sidebar active + 主面板渲染', async ({ page }) => {
    const faultBtn = page.locator('aside button:has-text("故障诊断")').first()
    await faultBtn.click()
    await page.waitForTimeout(500)

    await expect(faultBtn).toHaveClass(/bg-accent/)

    const mainContent = page.locator(MAIN_PANEL).first()
    await expect(mainContent).toContainText('故障', { timeout: 3000 })

    await page.screenshot({ path: 'e2e/screenshots/tab-fault.png' })
  })

  test('点击机器人 → sidebar active + 主面板渲染机器人控制', async ({ page }) => {
    const robotBtn = page.locator('aside button:has-text("机器人")').first()
    await robotBtn.click()
    await page.waitForTimeout(500)

    await expect(robotBtn).toHaveClass(/bg-accent/)

    const mainContent = page.locator(MAIN_PANEL).first()
    await expect(mainContent).toContainText('机器人控制', { timeout: 3000 })

    await page.screenshot({ path: 'e2e/screenshots/tab-robot.png' })
  })
})
