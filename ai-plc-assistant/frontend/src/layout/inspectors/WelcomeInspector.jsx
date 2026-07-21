// 欢迎页 Inspector — 工程信息 + 程序块 + 常用变量 + 工程搜索
import { useState } from 'react'
import { Cpu, Code2, Variable, Search } from 'lucide-react'
import { searchProjects } from '../../api'
import { PanelSection, KeyValue } from './shared'

export default function WelcomeInspector({ addLog, currentProject }) {
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
    <>
      <PanelSection title="当前工程" icon={Cpu}>
        <div className="space-y-1.5">
          <KeyValue k="项目" v={proj.name} />
          <KeyValue k="PLC" v={proj.plc_type} />
          <KeyValue k="TIA" v={proj.tia_version} />
          <KeyValue k="语言" v={proj.language} />
        </div>
      </PanelSection>

      <PanelSection title="程序块" icon={Code2}>
        {currentProject ? (
          <div className="text-xs text-text-dim">使用左侧工程搜索查找程序块</div>
        ) : (
          <div className="text-xs text-text-dim">请先选择项目</div>
        )}
      </PanelSection>

      <PanelSection title="常用变量" icon={Variable}>
        {currentProject ? (
          <div className="text-xs text-text-dim">使用工程搜索查找变量</div>
        ) : (
          <div className="text-xs text-text-dim">请先选择项目</div>
        )}
      </PanelSection>

      <PanelSection title="工程搜索" icon={Search} defaultOpen>
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
              <div key={r.name || i} className="p-2 bg-ide-panel rounded border border-ide-border text-2xs">
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
    </>
  )
}
