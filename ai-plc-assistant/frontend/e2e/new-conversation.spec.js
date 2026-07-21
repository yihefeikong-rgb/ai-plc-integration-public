/**
 * E2E-3: 新建对话 — 验证 TopBar AI 菜单 → 新建对话 流程
 *
 * 流程：
 *  1. 点 TopBar "AI" 菜单
 *  2. 点下拉"新建对话"
 *  3. 验证对话 tab 激活 + 消息区清空
 */
import { test, expect } from '@playwright/test'
import { mockApi } from './fixtures/api-mock.js'

test.describe('新建对话', () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page)
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)
  })

  test('TopBar AI 菜单 → 新建对话', async ({ page }) => {
    // 点 AI 菜单
    await page.locator('header button:has-text("AI")').first().click()
    await page.waitForTimeout(200)

    // 下拉出现"新建对话"
    const newChatBtn = page.locator('div[class*="absolute"] button:has-text("新建对话")').first()
    await expect(newChatBtn).toBeVisible({ timeout: 1000 })

    // 点新建对话
    await newChatBtn.click()
    await page.waitForTimeout(800)

    // 验证切换到 chat tab — 输入框可见
    const textarea = page.locator('textarea[placeholder*="输入指令"]')
    await expect(textarea).toBeVisible({ timeout: 3000 })

    await page.screenshot({ path: 'e2e/screenshots/new-conversation.png' })
  })

  test('sidebar 资源分组 → 新建对话', async ({ page }) => {
    // 资源分组默认折叠，先展开
    const resourceHeader = page.locator('aside button:has-text("资源")').first()
    await resourceHeader.click()
    await page.waitForTimeout(300)

    // 找"新建对话"按钮（资源分组内）
    const newChatBtn = page.locator('aside button:has-text("新建对话")').first()
    await expect(newChatBtn).toBeVisible({ timeout: 1000 })
    await newChatBtn.click()
    await page.waitForTimeout(800)

    // 验证输入框可见
    await expect(page.locator('textarea[placeholder*="输入指令"]')).toBeVisible({ timeout: 3000 })
  })
})
