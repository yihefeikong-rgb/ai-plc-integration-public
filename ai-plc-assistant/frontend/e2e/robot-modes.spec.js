/**
 * E2E-5: 机器人 4 模式切换 — 验证 F-019 安全边界
 *
 * 覆盖：
 *  - 4 模式按钮可点（演示/仿真/只读/真实控制）
 *  - 切换 readonly 后，写入按钮被禁用
 *  - 切换 real-control 后，未达 Safety Level L3 显示警告
 *
 * 关联：P2 完成的 F-019 机器人 4 模式 + guardWrite
 */
import { test, expect } from '@playwright/test'
import { mockApi } from './fixtures/api-mock.js'

test.describe('机器人 4 模式切换', () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page)
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    // 切到 robot tab
    await page.locator('aside button:has-text("机器人")').first().click()
    await page.waitForTimeout(500)
  })

  test('4 模式按钮可见', async ({ page }) => {
    await expect(page.locator('button:has-text("演示")').first()).toBeVisible()
    await expect(page.locator('button:has-text("仿真")').first()).toBeVisible()
    await expect(page.locator('button:has-text("只读")').first()).toBeVisible()
    await expect(page.locator('button:has-text("真实控制")').first()).toBeVisible()
  })

  test('切换到只读模式 — 写入按钮 disabled', async ({ page }) => {
    // 默认是仿真模式（simulation），点只读切换
    await page.locator('button:has-text("只读")').first().click()
    await page.waitForTimeout(300)

    // 验证"拾取"按钮 disabled
    const pickBtn = page.locator('button:has-text("拾取")').first()
    await expect(pickBtn).toBeDisabled({ timeout: 2000 })

    // 截图 readonly 状态
    await page.screenshot({ path: 'e2e/screenshots/robot-readonly.png' })
  })

  test('切换到真实控制 — 显示 Safety Level 警告', async ({ page }) => {
    // 清空 localStorage safety-level 确保未授权
    await page.evaluate(() => {
      try { localStorage.removeItem('ai-plc:safety-level') } catch {}
    })

    // 切到真实控制
    await page.locator('button:has-text("真实控制")').first().click()
    await page.waitForTimeout(300)

    // 验证警告出现（F-019 未达 L3 时显示）
    await expect(page.locator('text=真实控制模式需要 Safety Level')).toBeVisible({ timeout: 2000 })

    await page.screenshot({ path: 'e2e/screenshots/robot-real-control-warn.png' })
  })

  test('仿真模式 — 写入按钮可点', async ({ page }) => {
    // 默认就是仿真，点回仿真
    await page.locator('button:has-text("仿真")').first().click()
    await page.waitForTimeout(300)

    // 验证"拾取"按钮 enabled
    const pickBtn = page.locator('button:has-text("拾取")').first()
    await expect(pickBtn).toBeEnabled({ timeout: 2000 })

    await page.screenshot({ path: 'e2e/screenshots/robot-simulation.png' })
  })
})
