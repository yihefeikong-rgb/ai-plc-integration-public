/**
 * E2E-4: 发送消息 + SSE 流式响应 — 验证 chat 端到端流程
 *
 * 流程：
 *  1. 新建对话
 *  2. 输入"你好"
 *  3. 按 Enter 发送（ChatArea.jsx onKeyDown 处理 Enter）
 *  4. 验证 SSE mock 流式 token 出现在消息区
 *
 * mock：streamChat 端点用 page.route() 拦截，返回 3 个 token "你好！"
 */
import { test, expect } from '@playwright/test'
import { mockApi } from './fixtures/api-mock.js'

const MAIN_PANEL = 'div.flex-1.flex.overflow-hidden > div.flex-1'

test.describe('发送消息 — SSE 流式', () => {
  test.beforeEach(async ({ page }) => {
    // mockApi 直接处理 SSE，传 streamTokens
    await mockApi(page, { streamTokens: ['你', '好', '！'] })
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    // 先新建对话
    await page.locator('header button:has-text("AI")').first().click()
    await page.waitForTimeout(200)
    await page.locator('div[class*="absolute"] button:has-text("新建对话")').first().click()
    await page.waitForTimeout(800)
  })

  test('输入"你好" → 发送 → SSE 流式输出', async ({ page }) => {
    const textarea = page.locator('textarea[placeholder*="输入指令"]')
    await expect(textarea).toBeVisible({ timeout: 3000 })

    // 输入文本
    await textarea.fill('你好')

    // 按 Enter 发送（ChatArea.jsx 中 onKeyDown 处理 Enter，无 Shift）
    await textarea.press('Enter')

    // 验证用户消息出现
    await expect(page.locator(MAIN_PANEL).first()).toContainText('你好', { timeout: 3000 })

    // 验证 SSE 流式 token 出现（最长 5s，mock 3 token "你好！"）
    await expect(page.locator(MAIN_PANEL).first()).toContainText('你好！', { timeout: 5000 })

    await page.screenshot({ path: 'e2e/screenshots/chat-send-message.png' })
  })

  test('发送按钮可见 + disabled 状态正确', async ({ page }) => {
    const textarea = page.locator('textarea[placeholder*="输入指令"]')
    await expect(textarea).toBeVisible({ timeout: 3000 })

    // 输入框空时发送按钮 disabled
    const sendBtn = page.locator('button[type="submit"]:has-text("发送")')
    await expect(sendBtn).toBeDisabled()

    // 输入文本后 enabled
    await textarea.fill('测试')
    await expect(sendBtn).toBeEnabled()

    // 清空后再次 disabled
    await textarea.fill('')
    await expect(sendBtn).toBeDisabled()
  })
})
