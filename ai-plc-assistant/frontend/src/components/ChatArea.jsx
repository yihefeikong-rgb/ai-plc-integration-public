import { useState, useRef, useEffect } from 'react'
import {
  Send, Bot, User, BookOpen, Download, FileCode, FileText as FileXml,
  Table2, ArrowDown, Eye, Code, Square, FileText, Paperclip, AtSign,
  AlertTriangle, Info, CheckCircle2, Loader2, File as FileIcon,
} from 'lucide-react'
import { exportCode } from '../api'
import ReactMarkdown from 'react-markdown'
import LadderVisualizer from './LadderVisualizer'

/**
 * ChatArea — 工程 AI 工作区（Batch 6 重构）
 *
 * 按主计划 §9：
 * - §9.2 消息类型 13 种：text/markdown/code/variables/io-table/ladder/
 *   task-progress/tool-call/file/warning/error/export-result/citation
 * - §9.3 输入区：当前项目/当前模型/模板/附件/引用工程/输入框/发送/停止生成
 * - §9.4 SSE 状态：当前模型/生成中/停止按钮/已生成内容/错误或回退
 * - §9.5 ASCII-LAD 默认显示（F-026 修复），SVG 不再默认
 */

const MSG_TYPES = {
  TEXT: 'text',
  MARKDOWN: 'markdown',
  CODE: 'code',
  VARIABLES: 'variables',
  IO_TABLE: 'io-table',
  LADDER: 'ladder',
  TASK_PROGRESS: 'task-progress',
  TOOL_CALL: 'tool-call',
  FILE: 'file',
  WARNING: 'warning',
  ERROR: 'error',
  EXPORT_RESULT: 'export-result',
  CITATION: 'citation',
}

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
  // F-026 修复：ASCII-LAD 默认显示（textMode=true），SVG 不再默认
  const [textMode, setTextMode] = useState(true)

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
          <div className="flex items-center justify-between">
            <div className="text-2xs font-medium text-text-secondary uppercase tracking-wider">程序逻辑</div>
            <button
              type="button"
              onClick={() => setTextMode(!textMode)}
              className="flex items-center gap-1 px-2 py-0.5 text-2xs text-text-dim hover:text-accent border border-transparent hover:border-accent/40 rounded transition-colors"
              title={textMode ? '显示图形' : '显示源码'}
            >
              {textMode ? <Eye size={12} /> : <Code size={12} />}
              {textMode ? '图形' : '源码'}
            </button>
          </div>
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
              {n.code && textMode && (
                <pre className="px-3 py-2 text-xs text-text-secondary font-mono leading-relaxed overflow-x-auto bg-ide-panel">
                  {n.code}
                </pre>
              )}
              {n.code && !textMode && (
                <LadderVisualizer code={n.code} networkTitle={`Network ${n.number}: ${n.title}`} />
              )}
            </div>
          ))}
        </div>
      )}

      {structured && (
        <div className="flex items-center gap-2 pt-2 border-t border-ide-border">
          <span className="text-2xs text-text-dim mr-1">导出:</span>
          <button type="button" onClick={() => handleExport(structured, 'scl', title)}
            className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent transition-colors text-text-secondary">
            <FileCode size={12} /> SCL
          </button>
          <button type="button" onClick={() => handleExport(structured, 'xml', title)}
            className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent transition-colors text-text-secondary">
            <FileXml size={12} /> XML
          </button>
          <button type="button" onClick={() => handleExport(structured, 'csv', title)}
            className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent transition-colors text-text-secondary">
            <Table2 size={12} /> CSV
          </button>
          <button type="button" onClick={() => handleExport(structured, 'hmi', title)}
            className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent transition-colors text-text-secondary">
            <Download size={12} /> HMI
          </button>
        </div>
      )}
    </div>
  )
}

function PlaceholderMessage({ type, content }) {
  const labels = {
    [MSG_TYPES.IO_TABLE]: { icon: Table2, label: 'IO 表', desc: '待接入（将显示设备 IO 地址表）' },
    [MSG_TYPES.VARIABLES]: { icon: AtSign, label: '变量表', desc: '待接入（将显示变量分析结果）' },
    [MSG_TYPES.TASK_PROGRESS]: { icon: Loader2, label: '任务进度', desc: '待接入（将显示后台任务进度）' },
    [MSG_TYPES.TOOL_CALL]: { icon: FileCode, label: '工具调用', desc: '待接入（将显示工具调用详情）' },
    [MSG_TYPES.FILE]: { icon: FileIcon, label: '文件', desc: '待接入（将显示文件附件）' },
    [MSG_TYPES.EXPORT_RESULT]: { icon: Download, label: '导出结果', desc: '待接入（将显示导出文件下载）' },
    [MSG_TYPES.CITATION]: { icon: BookOpen, label: '引用来源', desc: '待接入（将显示知识库引用）' },
  }
  const info = labels[type] || { icon: Info, label: type, desc: '未接入' }
  const Icon = info.icon
  return (
    <div className="flex items-start gap-2 p-3 bg-ide-panel/50 border border-ide-border rounded">
      <Icon size={14} className="text-text-dim shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="text-2xs font-medium text-text-secondary uppercase tracking-wider mb-0.5">{info.label}</div>
        <div className="text-2xs text-text-dim">{info.desc}</div>
        {content && <div className="text-2xs text-text-dim mt-1 truncate">{String(content).slice(0, 200)}</div>}
      </div>
    </div>
  )
}

function WarningMessage({ content }) {
  return (
    <div className="flex items-start gap-2 p-3 bg-status-warning/10 border border-status-warning/30 rounded">
      <AlertTriangle size={14} className="text-status-warning shrink-0 mt-0.5" />
      <div className="flex-1 text-xs text-status-warning whitespace-pre-wrap">{content}</div>
    </div>
  )
}

function ErrorMessage({ content }) {
  return (
    <div className="flex items-start gap-2 p-3 bg-status-error/10 border border-status-error/30 rounded">
      <AlertTriangle size={14} className="text-status-error shrink-0 mt-0.5" />
      <div className="flex-1 text-xs text-status-error whitespace-pre-wrap">{content}</div>
    </div>
  )
}

function MessageBlock({ msg }) {
  const isUser = msg.role === 'user'
  const msgType = msg.type || MSG_TYPES.TEXT

  return (
    <div className={`border-b border-ide-border ${isUser ? 'bg-ide-bg' : 'bg-ide-sidebar/50'}`}>
      <div className="max-w-4xl mx-auto px-4 py-3">
        <div className="flex items-center gap-2 mb-2">
          {isUser ? (
            <User size={14} className="text-text-dim" />
          ) : (
            <Bot size={14} className="text-accent" />
          )}
          <span className="text-2xs font-medium text-text-dim uppercase tracking-wider">
            {isUser ? '输入' : 'AI 助手'}
          </span>
          {msg.fallback && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-2xs bg-status-warning/15 text-status-warning border border-status-warning/30">
              已切换至 {msg.model || '备用模型'}
            </span>
          )}
          {msg.model && !msg.fallback && !isUser && (
            <span className="text-2xs text-text-dim">{msg.model}</span>
          )}
          {msg.stopped && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-2xs bg-ide-panel text-text-dim border border-ide-border">
              已停止
            </span>
          )}
          {msg.streaming && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-2xs text-accent animate-pulse">
              生成中...
            </span>
          )}
          {msg.rag_sources?.length > 0 && (
            <span className="flex items-center gap-1 text-2xs text-status-info ml-auto">
              <BookOpen size={11} /> 引用 {msg.rag_sources.length} 个文档
            </span>
          )}
        </div>

        {isUser ? (
          <div className="text-sm text-text-primary whitespace-pre-wrap">{msg.content}</div>
        ) : msgType === MSG_TYPES.LADDER ? (
          <LadderResult msg={msg} />
        ) : msgType === MSG_TYPES.WARNING ? (
          <WarningMessage content={msg.content} />
        ) : msgType === MSG_TYPES.ERROR ? (
          <ErrorMessage content={msg.content} />
        ) : [MSG_TYPES.IO_TABLE, MSG_TYPES.VARIABLES, MSG_TYPES.TASK_PROGRESS,
             MSG_TYPES.TOOL_CALL, MSG_TYPES.FILE, MSG_TYPES.EXPORT_RESULT,
             MSG_TYPES.CITATION].includes(msgType) ? (
          <PlaceholderMessage type={msgType} content={msg.content} />
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

function ChatInput({
  input, setInput, onSubmit, onKeyDown, sending, onStop,
  currentProject, selectedModel, onOpenTemplates, onAddAttachment,
}) {
  return (
    <div className="border-t border-ide-border bg-ide-sidebar">
      {/* §9.4 SSE 状态栏：当前项目 + 当前模型 + 生成状态 */}
      <div className="flex items-center gap-3 px-4 py-1.5 border-b border-ide-border text-2xs">
        <span className="text-text-dim">
          项目: <span className="text-text-secondary font-mono">{currentProject?.name || '未选择'}</span>
        </span>
        <span className="text-text-dim">·</span>
        <span className="text-text-dim">
          模型: <span className="text-text-secondary font-mono">{selectedModel || '-'}</span>
        </span>
        {sending && (
          <span className="flex items-center gap-1 text-accent ml-auto">
            <Loader2 size={11} className="animate-spin" />
            生成中
          </span>
        )}
      </div>

      {/* §9.3 输入区 */}
      <form onSubmit={onSubmit} className="max-w-4xl mx-auto p-3 flex gap-2 items-end">
        {/* 二级菜单：模板 / 附件 / 引用工程 */}
        <button
          type="button"
          onClick={onOpenTemplates}
          title="提示词模板"
          className="px-2 py-2 text-text-dim hover:text-accent border border-ide-border rounded transition-colors"
        >
          <FileText size={14} />
        </button>
        <button
          type="button"
          onClick={onAddAttachment}
          title="附件（待接入）"
          className="px-2 py-2 text-text-dim hover:text-accent border border-ide-border rounded transition-colors"
        >
          <Paperclip size={14} />
        </button>
        <button
          type="button"
          title={`引用工程: ${currentProject?.name || '未选择'}`}
          className="px-2 py-2 text-text-dim hover:text-accent border border-ide-border rounded transition-colors"
        >
          <AtSign size={14} />
        </button>

        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={sending}
          placeholder={sending ? '处理中...' : '输入指令或 PLC 编程需求... (Enter 发送, Shift+Enter 换行)'}
          rows={1}
          className="flex-1 bg-ide-input border border-ide-border rounded px-3 py-2 text-sm text-text-primary placeholder-text-dim outline-none focus:border-accent transition-colors disabled:opacity-50 resize-none min-h-[38px] max-h-32"
        />

        {sending ? (
          <button
            type="button"
            onClick={onStop}
            className="px-4 py-2 bg-status-error text-white rounded text-xs font-medium hover:bg-status-error/90 transition-colors flex items-center gap-1.5"
          >
            <Square size={13} /> 停止
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim()}
            className="px-4 py-2 bg-accent text-white rounded text-xs font-medium hover:bg-accent-hover disabled:opacity-30 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
          >
            <Send size={13} /> 发送
          </button>
        )}
      </form>
    </div>
  )
}

export default function ChatArea({
  messages,
  onSend,
  onStop,
  initialInput = '',
  sending = false,
  currentProject,
  selectedModel,
  onOpenTemplates,
  onAddAttachment,
}) {
  const [input, setInput] = useState(initialInput)
  const [showScrollBtn, setShowScrollBtn] = useState(false)
  const endRef = useRef(null)
  const scrollRef = useRef(null)
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

  const handleScroll = () => {
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100
    setShowScrollBtn(!atBottom)
  }

  const scrollToBottom = () => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

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
      <div className="flex-1 overflow-hidden relative">
        <div ref={scrollRef} onScroll={handleScroll} className="h-full overflow-y-auto">
          {messages.length === 0 ? (
            <div className="h-full flex items-center justify-center text-text-dim text-xs">
              <div className="text-center">
                <Bot size={32} className="mx-auto mb-2 opacity-50" />
                <div>开始新的 AI 对话</div>
                <div className="text-2xs mt-1">输入需求或选择模板</div>
              </div>
            </div>
          ) : (
            messages.map((msg, i) => (
              <MessageBlock key={i} msg={msg} />
            ))
          )}
          <div ref={endRef} />
        </div>
        {showScrollBtn && (
          <button
            type="button"
            onClick={scrollToBottom}
            className="absolute bottom-4 right-6 w-8 h-8 bg-ide-panel border border-ide-border rounded-full flex items-center justify-center text-text-dim hover:text-accent hover:border-accent/40 shadow-lg transition-colors"
          >
            <ArrowDown size={16} />
          </button>
        )}
      </div>

      <ChatInput
        input={input}
        setInput={setInput}
        onSubmit={handleSubmit}
        onKeyDown={handleKeyDown}
        sending={sending}
        onStop={onStop}
        currentProject={currentProject}
        selectedModel={selectedModel}
        onOpenTemplates={onOpenTemplates}
        onAddAttachment={onAddAttachment}
      />
    </main>
  )
}
