import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, BookOpen, Download, FileCode, FileText as FileXml, Table2 } from 'lucide-react'
import { exportCode } from '../api'
import ReactMarkdown from 'react-markdown'

function downloadFile(content, filename, mime = 'text/plain') {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function handleExport(structured, format, title) {
  try {
    const data = await exportCode({
      title: title || 'export',
      variables: structured.variables || [],
      networks: structured.networks || [],
      format,
      block_type: 'FB',
      block_name: title || 'GeneratedBlock',
    })
    downloadFile(data.content, data.filename, data.mime_type)
  } catch (err) {
    alert('导出失败: ' + err.message)
  }
}

function LadderResult({ msg }) {
  const { title, description, structured } = msg
  const { variables, networks } = structured || {}

  return (
    <div className="space-y-3">
      <div className="text-sm font-medium text-accent">{title}</div>
      {description && <div className="text-2xs text-text-dim">{description}</div>}

      {variables?.length > 0 && (
        <div>
          <div className="text-2xs font-medium text-text-secondary mb-1 uppercase tracking-wider">变量表</div>
          <div className="overflow-x-auto border border-ide-border rounded">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-ide-panel text-text-dim border-b border-ide-border">
                  <th className="text-left px-3 py-1.5">地址</th>
                  <th className="text-left px-3 py-1.5">符号</th>
                  <th className="text-left px-3 py-1.5">类型</th>
                  <th className="text-left px-3 py-1.5">注释</th>
                </tr>
              </thead>
              <tbody>
                {variables.map((v, i) => (
                  <tr key={i} className="border-b border-ide-border last:border-0 text-text-secondary">
                    <td className="px-3 py-1 font-mono text-accent">{v.address}</td>
                    <td className="px-3 py-1 font-mono">{v.name}</td>
                    <td className="px-3 py-1">{v.data_type}</td>
                    <td className="px-3 py-1 text-text-dim">{v.comment}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {networks?.length > 0 && (
        <div className="space-y-2">
          <div className="text-2xs font-medium text-text-secondary uppercase tracking-wider">程序逻辑</div>
          {networks.map((n, i) => (
            <div key={i} className="border border-ide-border rounded overflow-hidden">
              <div className="px-3 py-1.5 bg-ide-panel border-b border-ide-border flex items-center gap-2">
                <span className="text-2xs font-mono text-accent">Network {n.number}</span>
                <span className="text-xs text-text-primary">{n.title}</span>
              </div>
              {n.comment && (
                <div className="px-3 py-1 text-2xs text-text-dim border-b border-ide-border">
                  // {n.comment}
                </div>
              )}
              {n.code && (
                <pre className="px-3 py-2 text-xs text-text-secondary font-mono leading-relaxed overflow-x-auto bg-ide-panel">
                  {n.code}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Export buttons */}
      {structured && (
        <div className="flex items-center gap-2 pt-2 border-t border-ide-border">
          <span className="text-2xs text-text-dim mr-1">导出:</span>
          <button onClick={() => handleExport(structured, 'scl', title)}
            className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent transition-colors text-text-secondary">
            <FileCode size={12} /> SCL
          </button>
          <button onClick={() => handleExport(structured, 'xml', title)}
            className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent transition-colors text-text-secondary">
            <FileXml size={12} /> XML
          </button>
          <button onClick={() => handleExport(structured, 'csv', title)}
            className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent transition-colors text-text-secondary">
            <Table2 size={12} /> CSV
          </button>
          <button onClick={() => handleExport(structured, 'hmi', title)}
            className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent transition-colors text-text-secondary">
            <Download size={12} /> HMI
          </button>
        </div>
      )}
    </div>
  )
}

function MessageBlock({ msg }) {
  const isUser = msg.role === 'user'

  return (
    <div className={`border-b border-ide-border ${isUser ? 'bg-ide-bg' : 'bg-ide-sidebar/50'}`}>
      <div className="max-w-4xl mx-auto px-4 py-3">
        {/* Header */}
        <div className="flex items-center gap-2 mb-2">
          {isUser ? (
            <User size={14} className="text-text-dim" />
          ) : (
            <Bot size={14} className="text-accent" />
          )}
          <span className="text-2xs font-medium text-text-dim uppercase tracking-wider">
            {isUser ? '输入' : 'AI 助手'}
          </span>
          {msg.rag_sources?.length > 0 && (
            <span className="flex items-center gap-1 text-2xs text-status-info ml-auto">
              <BookOpen size={11} /> 引用 {msg.rag_sources.length} 个文档
            </span>
          )}
        </div>

        {/* Content */}
        {isUser ? (
          <div className="text-sm text-text-primary whitespace-pre-wrap">{msg.content}</div>
        ) : msg.type === 'ladder' ? (
          <LadderResult msg={msg} />
        ) : (
          <div className="prose prose-invert max-w-none prose-sm text-text-primary
                          prose-code:bg-ide-panel prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-accent
                          prose-pre:bg-ide-panel prose-pre:border prose-pre:border-ide-border prose-pre:rounded
                          prose-headings:text-text-bright prose-a:text-accent">
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  )
}

export default function ChatArea({ messages, onSend, initialInput = '', sending = false }) {
  const [input, setInput] = useState(initialInput)
  const endRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (initialInput) {
      setInput(initialInput)
      inputRef.current?.focus()
    }
  }, [initialInput])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || sending) return
    onSend(text)
    setInput('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <main className="flex-1 flex flex-col overflow-hidden bg-ide-bg">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        {messages.map((msg, i) => (
          <MessageBlock key={i} msg={msg} />
        ))}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="border-t border-ide-border bg-ide-sidebar p-3">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={sending}
            placeholder={sending ? '处理中...' : '输入指令或PLC编程需求...'}
            className="flex-1 bg-ide-input border border-ide-border rounded px-3 py-2 text-sm text-text-primary placeholder-text-dim outline-none focus:border-accent transition-colors disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="px-4 py-2 bg-accent text-white rounded text-xs font-medium hover:bg-accent-hover disabled:opacity-30 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
          >
            <Send size={13} />
            {sending ? '处理中' : '发送'}
          </button>
        </form>
      </div>
    </main>
  )
}
