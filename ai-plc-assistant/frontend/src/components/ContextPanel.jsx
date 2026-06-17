import { useState } from 'react'
import {
  ChevronDown, ChevronRight, Cpu, Code2,
  Variable, Search,
} from 'lucide-react'
import { searchProjects } from '../api'

function PanelSection({ title, icon: Icon, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border-b border-ide-border">
      <button
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

export default function ContextPanel({ addLog, currentProject }) {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)

  const proj = currentProject || { name: '未选择', plc_type: '-', tia_version: '-', language: '-' }

  const handleSearch = async (e) => {
    e.preventDefault()
    const q = searchQuery.trim()
    if (!q) return
    setSearching(true)
    addLog?.('info', `[搜索] "${q}"`)
    try {
      const data = await searchProjects(q, '', 10)
      setSearchResults(data.results || [])
      addLog?.('info', `[搜索] ${data.total} 条结果`)
    } catch (err) {
      addLog?.('error', `[搜索] ${err.message}`)
      setSearchResults([])
    }
    setSearching(false)
  }

  return (
    <aside className="w-[320px] bg-ide-sidebar border-l border-ide-border flex flex-col shrink-0 overflow-hidden">
      <div className="flex-1 overflow-y-auto">
        {/* 当前工程 */}
        <PanelSection title="当前工程" icon={Cpu}>
          <div className="space-y-1.5 text-xs">
            {Object.entries({
              '项目': proj.name,
              'PLC': proj.plc_type,
              'TIA': proj.tia_version,
              '语言': proj.language,
            }).map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <span className="text-text-dim">{k}</span>
                <span className="text-text-secondary font-mono">{v}</span>
              </div>
            ))}
          </div>
        </PanelSection>

        {/* 程序块 */}
        <PanelSection title="程序块" icon={Code2}>
          {currentProject ? (
            <div className="text-xs text-text-dim">使用左侧工程搜索查找程序块</div>
          ) : (
            <div className="text-xs text-text-dim">请先选择项目</div>
          )}
        </PanelSection>

        {/* 变量 */}
        <PanelSection title="常用变量" icon={Variable}>
          {currentProject ? (
            <div className="text-xs text-text-dim">使用工程搜索查找变量</div>
          ) : (
            <div className="text-xs text-text-dim">请先选择项目</div>
          )}
        </PanelSection>

        {/* 工程搜索 */}
        <PanelSection title="工程搜索" icon={Search} defaultOpen={true}>
          <form onSubmit={handleSearch} className="mb-2">
            <div className="flex gap-1.5">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="搜索块、变量、注释..."
                className="flex-1 bg-ide-input border border-ide-border rounded px-2 py-1 text-xs text-text-primary placeholder-text-dim outline-none focus:border-accent"
              />
              <button
                type="submit"
                disabled={searching || !searchQuery.trim()}
                className="px-2 py-1 bg-accent text-white rounded text-xs disabled:opacity-30"
              >
                {searching ? '...' : '搜索'}
              </button>
            </div>
          </form>
          {searchResults.length > 0 && (
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {searchResults.map((r, i) => (
                <div key={i} className="p-2 bg-ide-panel rounded border border-ide-border text-2xs">
                  <div className="flex items-center gap-1 mb-0.5">
                    <span className="font-mono text-accent">{r.name}</span>
                    <span className="text-text-dim">{r.type}</span>
                  </div>
                  <div className="text-text-dim truncate">{r.content?.slice(0, 80)}</div>
                </div>
              ))}
            </div>
          )}
        </PanelSection>
      </div>
    </aside>
  )
}
