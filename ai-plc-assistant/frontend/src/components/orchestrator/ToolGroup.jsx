// 按服务器分组的工具列表
import { useState } from 'react'
import { ChevronDown, ChevronRight, Server, Wrench } from 'lucide-react'
import { cn, SERVER_CN, TOOL_CN, CATEGORY_CN } from './constants'

export default function ToolGroup({ server, tools, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div>
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-1.5 px-3 py-1.5 text-2xs font-semibold uppercase tracking-wider text-text-dim hover:text-text-secondary">
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <Server size={12} />
        <span>{cn(server, SERVER_CN) || server}</span>
        <span className="ml-auto text-text-dim font-normal">{tools.length}</span>
      </button>
      {open && tools.map(t => (
        <div key={t.name} className="flex items-center gap-2 pl-7 pr-3 py-1 text-xs text-text-secondary hover:bg-ide-hover">
          <Wrench size={12} className="text-text-dim shrink-0" />
          <span className="flex-1 truncate">{cn(t.name, TOOL_CN)}</span>
          <span className="text-2xs text-text-dim font-mono truncate max-w-[120px]">{t.name}</span>
          {t.category && (
            <span className="text-2xs px-1.5 py-0.5 rounded bg-ide-bg text-text-dim border border-ide-border shrink-0">
              {cn(t.category, CATEGORY_CN)}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}
