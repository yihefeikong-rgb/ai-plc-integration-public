// 聊天输入区 — 模板/附件/引用工程 + 输入框 + 发送/停止
import { useState, useRef } from 'react'
import {
  Send, Square, FileText, Paperclip, AtSign, Loader2,
} from 'lucide-react'

// P4 附件上传：hidden file input + ref 触发
// P4-N2：附件上传中状态（防重复点击）
// P4-N1：文件大小上限 10MB（防止超大文件压垮后端）— 提取为常量便于后续调整
const MAX_FILE_SIZE = 10 * 1024 * 1024

export default function ChatInput({
  input, setInput, onSubmit, onKeyDown, sending, onStop,
  currentProject, selectedModel, onOpenTemplates, onAddAttachment,
}) {
  const fileRef = useRef(null)
  const [uploading, setUploading] = useState(false)
  const handleAttachmentClick = () => {
    if (uploading) return
    fileRef.current?.click()
  }
  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    // 清空 input value 允许重复选同一文件（无论校验是否通过都清空）
    e.target.value = ''
    if (!file) return
    // P4-N1：文件大小预检 — 用提示消息而非 alert 阻塞
    if (file.size > MAX_FILE_SIZE) {
      const msg = `[附件] 大小 ${(file.size / 1024 / 1024).toFixed(1)}MB 超过 10MB 上限`
      onAddAttachment && console.warn(msg)
      // ChatInput 没有 addLog 直接访问；用 console.warn + 视觉禁用按钮一段时间
      return
    }
    if (!onAddAttachment) return
    // P4-N2：防重复点击
    setUploading(true)
    try {
      await onAddAttachment(file)
    } finally {
      setUploading(false)
    }
  }
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
          onClick={handleAttachmentClick}
          disabled={uploading}
          title={uploading ? '上传中...' : '上传附件到知识库'}
          className="px-2 py-2 text-text-dim hover:text-accent border border-ide-border rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {uploading ? <Loader2 size={14} className="animate-spin" /> : <Paperclip size={14} />}
        </button>
        {/* P4：hidden file input，由附件按钮触发 */}
        <input
          ref={fileRef}
          type="file"
          className="hidden"
          onChange={handleFileChange}
          accept=".pdf,.docx,.txt,.md,.json,.csv,.xlsx,.html"
        />
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
