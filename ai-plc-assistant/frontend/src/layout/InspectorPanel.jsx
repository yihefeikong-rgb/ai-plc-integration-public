import { useState } from 'react'
import {
  ChevronDown, ChevronRight, Cpu, Code2, Variable, Search,
  Bot, Zap, Table2, FileSearch, AlertTriangle, Settings as SettingsIcon,
  Inbox, Server, FileText,
} from 'lucide-react'
import { searchProjects } from '../api'
import EmptyState from '../components/ui/EmptyState'

/**
 * InspectorPanel — 右侧检查器面板（按 activeTab 变化）
 *
 * 按主计划 §7.5 切换 8 种内容：
 * welcome / chat / ladder / io-table / parse / diagnose / orchestrator / settings
 *
 * "总览" Inspector 保留现有"当前工程 + 程序块 + 常用变量 + 工程搜索"。
 * 其余 Inspector Batch 4 仅实现骨架 + EmptyState，不接业务逻辑。
 */

function PanelSection({ title, icon: Icon, defaultOpen = true, children }) {
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

function WelcomeInspector({ addLog, currentProject }) {
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
        <div className="space-y-1.5 text-xs">
          {Object.entries({
            项目: proj.name,
            PLC: proj.plc_type,
            TIA: proj.tia_version,
            语言: proj.language,
          }).map(([k, v]) => (
            <div key={k} className="flex justify-between">
              <span className="text-text-dim">{k}</span>
              <span className="text-text-secondary font-mono">{v}</span>
            </div>
          ))}
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
    </>
  )
}

function PlaceholderInspector({ type, icon: Icon }) {
  const labels = {
    chat: { title: 'AI 助手上下文', desc: '模型、项目上下文、知识库引用、附件（待 Batch 6 接入）' },
    ladder: { title: '梯形图属性', desc: '变量、Network 列表、模板、导出配置（待 Batch 7 接入）' },
    'io-table': { title: 'IO 表属性', desc: '地址范围、分类、校验（待 Batch 7 接入）' },
    parse: { title: '程序解析属性', desc: '文件、语言、块类型、分析（待 Batch 7 接入）' },
    diagnose: { title: '故障诊断属性', desc: '现象、设备状态、排查步骤（待 Batch 7 接入）' },
    orchestrator: { title: '编排属性', desc: '工作流、Agent、工具、服务器（已在主区域显示）' },
    settings: { title: '设置说明', desc: '当前配置说明（待 Batch 8 接入）' },
    variables: { title: '变量分析属性', desc: '地址冲突、命名、未使用变量（待 Batch 7 接入）' },
  }
  const info = labels[type] || { title: 'Inspector', desc: '未接入' }
  return (
    <div className="p-3">
      <div className="flex items-center gap-2 px-2 py-2 text-2xs font-semibold uppercase tracking-wider text-text-dim border-b border-ide-border">
        {Icon && <Icon size={13} />}
        <span>{info.title}</span>
      </div>
      <div className="p-3">
        <EmptyState icon={Inbox} description={info.desc} />
      </div>
    </div>
  )
}

const INSPECTOR_MAP = {
  welcome: { component: WelcomeInspector, isCustom: true },
  chat: { icon: Bot },
  ladder: { icon: Zap },
  'io-table': { icon: Table2 },
  parse: { icon: FileSearch },
  diagnose: { icon: AlertTriangle },
  orchestrator: { icon: Server },
  settings: { icon: SettingsIcon },
  variables: { icon: Variable },
  robot: { icon: Cpu },
}

export default function InspectorPanel({ addLog, currentProject, activeTab }) {
  const inspector = INSPECTOR_MAP[activeTab] || INSPECTOR_MAP.welcome

  return (
    <aside className="w-full bg-ide-sidebar border-l border-ide-border flex flex-col shrink-0 overflow-hidden h-full">
      <div className="flex-1 overflow-y-auto">
        {inspector.isCustom ? (
          <inspector.component addLog={addLog} currentProject={currentProject} />
        ) : (
          <PlaceholderInspector type={activeTab} icon={inspector.icon} />
        )}
      </div>
    </aside>
  )
}
