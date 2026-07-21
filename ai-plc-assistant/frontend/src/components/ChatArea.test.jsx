import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, cleanup, fireEvent } from '@testing-library/react'

// jsdom 不实现 scrollIntoView，mock 一下避免 ChatArea useEffect 抛错
if (!window.HTMLElement.prototype.scrollIntoView) {
  window.HTMLElement.prototype.scrollIntoView = () => {}
}

// mock CodeViewer 以便验证 F-041 分发到 CodeMessage → CodeViewer
vi.mock('./ui/CodeViewer', () => ({
  default: ({ code, language, title }) => (
    <div data-testid="code-viewer" data-language={language} data-title={title || ''}>
      {code}
    </div>
  ),
}))
vi.mock('./ui/DataTable', () => ({
  default: ({ data }) => <div data-testid="data-table">rows={data.length}</div>,
}))
vi.mock('./ui/EmptyState', () => ({
  default: ({ description }) => <div data-testid="empty-state">{description}</div>,
}))
vi.mock('./ui/CodeBlock', () => ({
  default: ({ code }) => <div data-testid="code-block">{code}</div>,
}))
vi.mock('./LadderVisualizer', () => ({
  default: ({ code }) => <div data-testid="ladder-visualizer">{code}</div>,
}))
vi.mock('react-markdown', () => ({
  default: ({ children }) => <div data-testid="react-markdown">{children}</div>,
}))

import ChatArea from './chat/ChatArea'

afterEach(() => {
  cleanup()
})

// 辅助：渲染 ChatArea 并返回容器
function renderChatArea(messages, props = {}) {
  return render(
    <ChatArea
      messages={messages}
      onSend={vi.fn()}
      onStop={vi.fn()}
      sending={false}
      selectedModel="deepseek"
      onOpenTemplates={vi.fn()}
      onAddAttachment={vi.fn()}
      currentProject={null}
      {...props}
    />
  )
}

describe('ChatArea MessageBlock 分发', () => {
  it('F-041 修复：CODE 类型消息用 CodeViewer 渲染（非 ReactMarkdown）', () => {
    const messages = [
      {
        id: 'm1',
        role: 'assistant',
        type: 'code',
        content: JSON.stringify({ code: 'WHILE true DO', language: 'SCL', title: '循环示例' }),
      },
    ]
    const { getByTestId, queryByTestId } = renderChatArea(messages)
    // 应渲染 CodeViewer
    expect(getByTestId('code-viewer')).toBeTruthy()
    expect(getByTestId('code-viewer').textContent).toContain('WHILE true DO')
    expect(getByTestId('code-viewer').getAttribute('data-language')).toBe('SCL')
    expect(getByTestId('code-viewer').getAttribute('data-title')).toBe('循环示例')
    // 不应走 ReactMarkdown 分支
    expect(queryByTestId('react-markdown')).toBeNull()
  })

  it('F-041：CODE 类型 content 为字符串 code 字段时正常解析', () => {
    const messages = [
      {
        id: 'm2',
        role: 'assistant',
        type: 'code',
        content: '{"code":"A := B + C;","language":"SCL"}',
      },
    ]
    const { getByTestId } = renderChatArea(messages)
    expect(getByTestId('code-viewer').textContent).toContain('A := B + C;')
  })

  it('F-041：CODE 类型 content 无 code 字段时走 PlaceholderMessage', () => {
    const messages = [
      {
        id: 'm3',
        role: 'assistant',
        type: 'code',
        content: '{}',
      },
    ]
    const { queryByTestId } = renderChatArea(messages)
    // 无 code 字段应不渲染 CodeViewer
    expect(queryByTestId('code-viewer')).toBeNull()
  })

  it('TEXT 类型消息走 ReactMarkdown 分支', () => {
    const messages = [
      { id: 'm4', role: 'assistant', type: 'text', content: '**粗体**文本' },
    ]
    const { getByTestId, queryByTestId } = renderChatArea(messages)
    expect(getByTestId('react-markdown')).toBeTruthy()
    expect(queryByTestId('code-viewer')).toBeNull()
  })

  it('WARNING 类型消息渲染 WarningMessage', () => {
    const messages = [
      { id: 'm5', role: 'assistant', type: 'warning', content: '警告内容' },
    ]
    const { getByText } = renderChatArea(messages)
    expect(getByText('警告内容')).toBeTruthy()
  })

  it('ERROR 类型消息渲染 ErrorMessage', () => {
    const messages = [
      { id: 'm6', role: 'assistant', type: 'error', content: '错误内容' },
    ]
    const { getByText } = renderChatArea(messages)
    expect(getByText('错误内容')).toBeTruthy()
  })

  it('IO_TABLE 类型消息用 DataTable 渲染', () => {
    const messages = [
      {
        id: 'm7',
        role: 'assistant',
        type: 'io-table',
        content: JSON.stringify({
          rows: [
            { address: 'I0.0', name: 'Start', type: 'Bool', direction: 'input', comment: '启动' },
          ],
        }),
      },
    ]
    const { getByTestId } = renderChatArea(messages)
    expect(getByTestId('data-table').textContent).toContain('rows=1')
  })

  it('user 消息用纯文本渲染（非 ReactMarkdown）', () => {
    const messages = [
      { id: 'm8', role: 'user', content: '**不会渲染粗体**' },
    ]
    const { getByText, queryByTestId } = renderChatArea(messages)
    // 用户消息原样显示
    expect(getByText('**不会渲染粗体**')).toBeTruthy()
    expect(queryByTestId('react-markdown')).toBeNull()
  })

  it('F-041：CODE 消息 fallback 顺序 code > content > text', () => {
    const messages = [
      {
        id: 'm9',
        role: 'assistant',
        type: 'code',
        content: JSON.stringify({ text: 'FROM_TEXT_FIELD', content: 'FROM_CONTENT', code: 'FROM_CODE' }),
      },
    ]
    const { getByTestId } = renderChatArea(messages)
    // code 字段优先
    expect(getByTestId('code-viewer').textContent).toContain('FROM_CODE')
  })

  it('fallback 消息显示"已切换至"标签（用 text-status-warn 色板）', () => {
    const messages = [
      {
        id: 'm10',
        role: 'assistant',
        type: 'text',
        content: '回复内容',
        fallback: true,
        model: 'kimi',
      },
    ]
    const { getByText, container } = renderChatArea(messages)
    expect(getByText('已切换至 kimi')).toBeTruthy()
    // 验证用 text-status-warn（F-068a 色板统一）
    const fallbackBadge = container.querySelector('.text-status-warn')
    expect(fallbackBadge).toBeTruthy()
  })
})
