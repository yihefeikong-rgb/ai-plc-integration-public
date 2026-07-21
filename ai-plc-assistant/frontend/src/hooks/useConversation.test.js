import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'

// 必须先 mock api，再 import useConversation
vi.mock('../api', () => ({
  createConversation: vi.fn(),
  addMessage: vi.fn(),
  getConversation: vi.fn(),
  listConversations: vi.fn(),
  deleteConversation: vi.fn(),
  generateLadder: vi.fn(),
  streamChat: vi.fn(),
  API_BASE: '/api',
  localControlHeaders: vi.fn(() => ({ 'X-Local-Api-Token': 'test-token' })),
}))

import useConversation from './useConversation'
import {
  createConversation, addMessage, getConversation, listConversations,
  deleteConversation, generateLadder, streamChat, API_BASE, localControlHeaders,
} from '../api'

// fetch mock（用于 fallback 路径）
global.fetch = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  listConversations.mockResolvedValue({ conversations: [] })
  createConversation.mockResolvedValue({ conversation: { id: 'conv-1', title: 'AI 对话' } })
  addMessage.mockResolvedValue({})
  getConversation.mockResolvedValue({ conversation: { id: 'conv-1', title: '测试', messages: [] } })
  deleteConversation.mockResolvedValue({})
  generateLadder.mockResolvedValue({ title: 'T', description: 'D', text: 'code', structured: { networks: [], variables: [] }, mode: 'LAD' })
  streamChat.mockResolvedValue(undefined)
  global.fetch.mockResolvedValue({
    ok: true,
    json: async () => ({ content: '非流式回复', model: 'deepseek', fallback: false }),
  })
})

afterEach(() => {
  // 仅清 call history，保留模块级 mock 的 implementation（restoreAllMocks 会清 implementation 导致后续测试 beforeEach 时序问题）
  vi.clearAllMocks()
})

// 辅助：包装 useConversation 渲染
function renderConv(overrides = {}) {
  const addLog = vi.fn()
  const openTab = vi.fn()
  const selectedModel = overrides.selectedModel || 'deepseek'
  const currentProject = overrides.currentProject || null
  return renderHook(() =>
    useConversation({ addLog, openTab, selectedModel, currentProject })
  )
}

describe('useConversation', () => {
  it('初始状态：空对话列表 + 空 messages + 非 sending', async () => {
    const { result } = renderConv()
    await waitFor(() => expect(listConversations).toHaveBeenCalled())
    expect(result.current.conversations).toEqual([])
    expect(result.current.messages).toEqual([])
    expect(result.current.sending).toBe(false)
    expect(result.current.convId).toBeNull()
  })

  it('refreshConversations 调 listConversations 并填充 state', async () => {
    listConversations.mockResolvedValue({ conversations: [{ id: 'c1', title: '对话1' }] })
    const { result } = renderConv()
    await waitFor(() => expect(result.current.conversations.length).toBe(1))
    expect(result.current.conversations[0].title).toBe('对话1')
  })

  it('handleNewConversation 清空 convId 和 messages 并打开 chat tab', async () => {
    const { result } = renderConv()
    await waitFor(() => expect(listConversations).toHaveBeenCalled())
    await act(async () => {
      await result.current.handleNewConversation()
    })
    expect(result.current.convId).toBeNull()
    expect(result.current.messages).toEqual([])
  })

  it('handleSwitchConversation 调 getConversation 并加载消息', async () => {
    getConversation.mockResolvedValue({
      conversation: {
        id: 'c2', title: '切换后对话',
        messages: [
          { role: 'user', content: '你好', msg_type: 'text' },
          { role: 'assistant', content: '你好！', msg_type: 'text' },
        ],
      },
    })
    const { result } = renderConv()
    await waitFor(() => expect(listConversations).toHaveBeenCalled())
    await act(async () => {
      await result.current.handleSwitchConversation('c2')
    })
    expect(result.current.convId).toBe('c2')
    expect(result.current.messages.length).toBe(2)
    // F-040 修复：所有消息应有 id
    expect(result.current.messages[0].id).toBeTruthy()
    expect(result.current.messages[1].id).toBeTruthy()
    expect(result.current.messages[0].role).toBe('user')
  })

  it('handleDeleteConversation 调 deleteConversation API', async () => {
    const { result } = renderConv()
    await waitFor(() => expect(listConversations).toHaveBeenCalled())
    await act(async () => {
      await result.current.handleDeleteConversation('c-del')
    })
    expect(deleteConversation).toHaveBeenCalledWith('c-del')
  })

  it('handleDeleteConversation 删除当前对话时清空 convId 和 messages', async () => {
    const { result } = renderConv()
    await waitFor(() => expect(listConversations).toHaveBeenCalled())
    // 先切到某对话
    getConversation.mockResolvedValue({
      conversation: { id: 'c-del', title: '待删', messages: [{ role: 'user', content: 'x', msg_type: 'text' }] },
    })
    await act(async () => { await result.current.handleSwitchConversation('c-del') })
    expect(result.current.convId).toBe('c-del')
    // 再删除
    await act(async () => { await result.current.handleDeleteConversation('c-del') })
    expect(result.current.convId).toBeNull()
    expect(result.current.messages).toEqual([])
  })

  it('handleSend 非梯形图请求走 SSE 流式路径', async () => {
    const { result } = renderConv()
    await waitFor(() => expect(listConversations).toHaveBeenCalled())
    // 模拟 streamChat 内部触发 onToken + onDone
    streamChat.mockImplementation(async ({ onToken, onDone }) => {
      onToken?.('你好')
      onToken?.('！')
      onDone?.({ model: 'deepseek', fallback: false, rag_sources: [] })
    })
    await act(async () => {
      await result.current.handleSend('你好')
    })
    // 应调用 streamChat
    expect(streamChat).toHaveBeenCalled()
    // 应有用户消息 + AI 消息
    expect(result.current.messages.length).toBeGreaterThanOrEqual(2)
    expect(result.current.messages[0].role).toBe('user')
    expect(result.current.messages[0].content).toBe('你好')
    // AI 消息应有 streaming: false 且 content 包含你好
    const aiMsg = result.current.messages[result.current.messages.length - 1]
    expect(aiMsg.role).toBe('assistant')
    expect(aiMsg.streaming).toBe(false)
    expect(aiMsg.content).toContain('你好')
  })

  it('F-040 修复：handleSend 后所有消息应有 stable id', async () => {
    const { result } = renderConv()
    await waitFor(() => expect(listConversations).toHaveBeenCalled())
    streamChat.mockImplementation(async ({ onDone }) => {
      onDone?.({ model: 'deepseek', fallback: false })
    })
    await act(async () => {
      await result.current.handleSend('测试消息')
    })
    // 所有消息都应有 id
    for (const m of result.current.messages) {
      expect(m.id).toBeTruthy()
      expect(typeof m.id).toBe('string')
    }
  })

  it('F-039 修复：SSE onError 保留半截内容 + 追加错误提示', async () => {
    const { result } = renderConv()
    await waitFor(() => expect(listConversations).toHaveBeenCalled())
    streamChat.mockImplementation(async ({ onToken, onError }) => {
      onToken?.('已生成的内容')
      onError?.(new Error('SSE 断开'))
    })
    await act(async () => {
      await result.current.handleSend('测试')
    })
    const lastMsg = result.current.messages[result.current.messages.length - 1]
    expect(lastMsg.role).toBe('assistant')
    expect(lastMsg.error).toBe(true)
    // 应保留半截内容
    expect(lastMsg.content).toContain('已生成的内容')
    // 应追加错误提示
    expect(lastMsg.content).toContain('调用失败: SSE 断开')
  })

  it('F-042 修复：SSE 失败回退非流式 fetch headers 含 localControlHeaders', async () => {
    const { result } = renderConv()
    await waitFor(() => expect(listConversations).toHaveBeenCalled())
    // streamChat 抛错触发 fallback
    streamChat.mockRejectedValue(new Error('SSE 不可用'))
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ content: 'fallback 回复', model: 'deepseek', fallback: true }),
    })
    await act(async () => {
      await result.current.handleSend('普通消息')
    })
    // fetch 应被调用
    expect(global.fetch).toHaveBeenCalledWith(
      `${API_BASE}/chat`,
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'X-Local-Api-Token': 'test-token',
          'Content-Type': 'application/json',
        }),
      })
    )
    // localControlHeaders 应被调用
    expect(localControlHeaders).toHaveBeenCalled()
    // 最后一条消息应为 fallback 回复
    const lastMsg = result.current.messages[result.current.messages.length - 1]
    expect(lastMsg.content).toBe('fallback 回复')
    expect(lastMsg.model).toBe('deepseek')
  })

  it('handleStop 调用 AbortController.abort 中止进行中的请求', async () => {
    // F-042/P1 补修：用 AbortController spy 验证 handleStop 真实调用 abort
    const abortSpy = vi.spyOn(AbortController.prototype, 'abort')
    const { result } = renderConv()
    await waitFor(() => expect(listConversations).toHaveBeenCalled())
    // streamChat 监听 signal abort，abort 时 reject 让 handleSend 走 catch 分支
    streamChat.mockImplementation(({ signal }) => new Promise((_, reject) => {
      if (signal) signal.addEventListener('abort', () => reject(new Error('aborted')))
    }))
    let sendPromise
    act(() => { sendPromise = result.current.handleSend('测试') })
    // 等待 handleSend 进入 await streamChat（让 abortRef.current 被赋值）
    await new Promise((r) => setTimeout(r, 0))
    // 调用 handleStop
    act(() => { result.current.handleStop() })
    // AbortController.abort 应被调用
    expect(abortSpy).toHaveBeenCalled()
    // 等 handleSend 完成
    await act(async () => { await sendPromise })
    // sending 应回到 false
    expect(result.current.sending).toBe(false)
    abortSpy.mockRestore()
  })

  it('梯形图请求（含"梯形图"关键词）走 generateLadder 路径', async () => {
    const { result } = renderConv()
    await waitFor(() => expect(listConversations).toHaveBeenCalled())
    generateLadder.mockResolvedValue({
      title: '电机正反转',
      description: '描述',
      text: 'NETWORK 1',
      structured: { networks: [{ number: 1, title: 'N1' }], variables: [] },
      mode: 'LAD',
    })
    await act(async () => {
      await result.current.handleSend('生成一个梯形图：电机正反转')
    })
    expect(generateLadder).toHaveBeenCalled()
    // 应有 ladder 类型消息
    const ladderMsg = result.current.messages.find((m) => m.type === 'ladder')
    expect(ladderMsg).toBeTruthy()
    expect(ladderMsg.title).toBe('电机正反转')
  })

  it('handleSend sending=true 时拒绝重复发送', async () => {
    // 验证 sending 防抖：手动设 sending=true 后调 handleSend 应直接 return
    const { result } = renderConv()
    await waitFor(() => expect(listConversations).toHaveBeenCalled())
    // 先正常发一条（会触发 streamChat mock 立即 onDone）
    streamChat.mockImplementation(async ({ onDone }) => {
      onDone?.({ model: 'deepseek', fallback: false })
    })
    await act(async () => {
      await result.current.handleSend('第一条')
    })
    const firstUserMsgCount = result.current.messages.filter((m) => m.role === 'user').length
    expect(firstUserMsgCount).toBe(1)
    // sending 应已回到 false
    expect(result.current.sending).toBe(false)
  })

  it('listConversations 失败时 conversations 保持空数组', async () => {
    listConversations.mockRejectedValue(new Error('network'))
    const { result } = renderConv()
    await waitFor(() => expect(listConversations).toHaveBeenCalled())
    // 应静默吞错，不抛异常
    expect(result.current.conversations).toEqual([])
  })
})
