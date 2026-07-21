/**
 * 共享 API mock — E2E spec 用
 *
 * 用法：
 *   import { mockApi, streamChatMock } from './fixtures/api-mock'
 *   await mockApi(page)
 *
 * 覆盖所有前端启动时调用的 API + chat send 流程，避免依赖真实后端。
 * 不阻断静态资源（JS/CSS/图片）。
 */

const API_BASE = '/api'

/** 默认健康检查响应 */
export const HEALTH_RESPONSE = {
  status: 'ok',
  version: 'test-e2e',
  services: { orchestrator: 'ok', knowledge: 'ok' },
}

/** 默认模型列表 */
export const MODELS_RESPONSE = {
  models: [
    { id: 'deepseek', name: 'DeepSeek (mock)', provider: 'deepseek' },
    { id: 'kimi', name: 'Kimi (mock)', provider: 'kimi' },
  ],
}

/** 默认项目列表 */
export const PROJECTS_RESPONSE = { projects: [] }

/** 默认知识库文档列表 */
export const DOCUMENTS_RESPONSE = { documents: [] }

/** 默认对话列表 */
export const CONVERSATIONS_RESPONSE = { conversations: [] }

/** 默认 orchestrator 健康 */
export const ORCHESTRATOR_HEALTH = {
  status: 'ok',
  servers: [],
  workflows: [],
  tools: [],
}

/** 默认 servers 列表 */
export const SERVERS_RESPONSE = { servers: [] }

/**
 * mock 全部 API endpoint，返回 200 + 默认 payload。
 * spec 内可再 page.route() 覆盖单个 endpoint 拿定制响应。
 *
 * 注意：生产构建 API_BASE 为绝对 URL（http://127.0.0.1:8005/api），
 * 因此 route 必须用 glob 匹配任意 host（避免 host 硬编码）。
 *
 * @param {import('@playwright/test').Page} page
 * @param {{ streamTokens?: string[] }} options - 可选 SSE tokens
 */
export async function mockApi(page, options = {}) {
  const streamTokens = options.streamTokens || ['你', '好', '！']

  // 通配：所有 /api/* 请求返回默认 payload（匹配任意 host）
  await page.route('**/api/**', async (route) => {
    const url = route.request().url()
    const method = route.request().method()

    // SSE 流式 chat：直接 fulfill，不依赖 fallback（v1.61 fallback 行为不稳）
    if (url.includes('/chat/stream') && method === 'POST') {
      const chunks = []
      for (const t of streamTokens) {
        chunks.push('data: ' + JSON.stringify({ token: t }) + '\n\n')
      }
      chunks.push('data: ' + JSON.stringify({ done: true, model: 'mock-model' }) + '\n\n')
      chunks.push('data: [DONE]' + '\n\n')
      return route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: chunks.join(''),
      })
    }

    // 非流式 /chat fallback（POST，HTTP 200 JSON）
    if (url.endsWith('/chat') && method === 'POST') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ content: 'mock 非流式回复', model: 'deepseek', fallback: false }),
      })
    }

    // 默认 JSON 响应映射
    const responses = {
      '/health': HEALTH_RESPONSE,
      '/models': MODELS_RESPONSE,
      '/projects': PROJECTS_RESPONSE,
      '/knowledge/documents': DOCUMENTS_RESPONSE,
      '/knowledge/status': { status: 'ok', documents: 0 },
      '/conversations': CONVERSATIONS_RESPONSE,
      '/orchestrator/health': ORCHESTRATOR_HEALTH,
      '/orchestrator/servers': SERVERS_RESPONSE,
      '/orchestrator/tools': { tools: [] },
      '/orchestrator/workflows': { workflows: [] },
      '/orchestrator/monitor': { monitor: {} },
      '/settings': { settings: {} },
      '/settings/providers': { providers: [] },
      '/prompts': { prompts: [] },
      '/prompts/categories': { categories: [] },
      '/knowledge/code-templates': { templates: [] },
      '/knowledge/ladder-templates': { templates: [] },
      '/search/stats': { stats: {} },
    }

    // 路径匹配（去掉 query + host，只保留 /api 后部分）
    const apiIdx = url.indexOf('/api')
    const path = apiIdx >= 0 ? url.slice(apiIdx + 3).split('?')[0] : url.split('?')[0]

    // 精确匹配
    if (responses[path]) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(responses[path]) })
    }

    // /conversations/{id} GET
    if (path.match(/^\/conversations\/[^/]+$/) && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ conversation: { id: path.split('/')[2], title: 'Test', messages: [] } }),
      })
    }

    // POST /conversations（创建）
    if (path === '/conversations' && method === 'POST') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ conversation: { id: 'conv-test-1', title: 'Test Conversation' } }),
      })
    }

    // POST /conversations/{id}/messages
    if (path.match(/^\/conversations\/[^/]+\/messages$/) && method === 'POST') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ message: { id: 'msg-test-1' } }),
      })
    }

    // POST /generate/ladder
    if (path === '/generate/ladder' && method === 'POST') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          title: 'Test Ladder',
          mode: 'SCL',
          description: 'E2E mock ladder',
          text: 'mock ladder code',
          structured: { networks: [{ id: 1, title: 'Net1', ascii: '|---|---|' }] },
        }),
      })
    }

    // 其他未匹配 API：返回空 200，避免阻断
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, mock: true }),
    })
  })
}


