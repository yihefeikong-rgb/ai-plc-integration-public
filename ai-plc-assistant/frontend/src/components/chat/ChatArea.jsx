// ChatArea — 工程 AI 工作区（Batch 6 重构）
//
// 按主计划 §9：
// - §9.2 消息类型 13 种：text/markdown/code/variables/io-table/ladder/
//   task-progress/tool-call/file/warning/error/export-result/citation
// - §9.3 输入区：当前项目/当前模型/模板/附件/引用工程/输入框/发送/停止生成
// - §9.4 SSE 状态：当前模型/生成中/停止按钮/已生成内容/错误或回退
// - §9.5 ASCII-LAD 默认显示（F-026 修复），SVG 不再默认
import { useState, useRef, useEffect } from 'react'
import { Bot, ArrowDown } from 'lucide-react'
import ChatInput from './ChatInput'
import MessageBlock from './messages/MessageBlock'

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
              <MessageBlock key={msg.id || `${i}-${msg.role}`} msg={msg} />
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
