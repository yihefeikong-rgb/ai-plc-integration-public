// InspectorPanel 共用组件与工具
import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

// 从 messages 中查找最近一条指定类型的消息
export function findLastMessageByType(messages, type) {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].type === type) return messages[i]
  }
  return null
}

// 容错解析消息 content：对象直接用，字符串尝试 JSON.parse，失败返回 {}
export function parseContent(content) {
  if (!content) return {}
  if (typeof content === 'string') {
    try {
      const parsed = JSON.parse(content)
      return typeof parsed === 'object' && parsed !== null ? parsed : {}
    } catch {
      return {}
    }
  }
  return content
}

export function PanelSection({ title, icon: Icon, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border-b border-ide-border">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-1.5 px-3 py-2 text-2xs font-semibold uppercase tracking-wider text-text-dim hover:text-text-secondary"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <Icon size={13} />
        <span>{title}</span>
      </button>
      {open && <div className="px-3 pb-3">{children}</div>}
    </div>
  )
}

export function KeyValue({ k, v, mono = true }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-text-dim">{k}</span>
      <span className={mono ? 'text-text-secondary font-mono' : 'text-text-secondary'}>{v ?? '-'}</span>
    </div>
  )
}
