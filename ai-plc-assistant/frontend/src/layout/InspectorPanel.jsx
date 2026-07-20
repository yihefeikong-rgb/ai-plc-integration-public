import { useState, useMemo } from 'react'
import {
  ChevronDown, ChevronRight, Cpu, Code2, Variable, Search,
  Bot, Zap, Table2, FileSearch, AlertTriangle, Settings as SettingsIcon,
  Inbox, Server, FileText, BookOpen, History, ListTree, AlertCircle,
} from 'lucide-react'
import { searchProjects } from '../api'
import EmptyState from '../components/ui/EmptyState'

/**
 * InspectorPanel — 右侧检查器面板（按 activeTab 变化，8 种内容）
 *
 * 按主计划 §7.5：welcome / chat / ladder / io-table / parse / diagnose / orchestrator / settings
 * D-3 填充：每种 Inspector 基于 currentProject + messages + selectedModel 显示结构化内容
 */

// 从 messages 中查找最近一条指定类型的消息
function findLastMessageByType(messages, type) {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].type === type) return messages[i]
  }
  return null
}

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

function KeyValue({ k, v, mono = true }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-text-dim">{k}</span>
      <span className={mono ? 'text-text-secondary font-mono' : 'text-text-secondary'}>{v ?? '-'}</span>
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

// D-3：AI 助手 Inspector — 当前模型 + 项目上下文 + 最近对话 + 知识库引用
function ChatInspector({ currentProject, selectedModel, messages, conversations }) {
  const lastAiMsg = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant') return messages[i]
    }
    return null
  }, [messages])
  const ragSources = lastAiMsg?.rag_sources || []
  const recentConvs = (conversations || []).slice(0, 5)

  return (
    <>
      <PanelSection title="当前模型" icon={Bot}>
        <div className="space-y-1.5">
          <KeyValue k="模型" v={selectedModel || '未选择'} />
          <KeyValue k="流式" v="SSE" />
          <KeyValue k="停止" v="AbortController" />
        </div>
      </PanelSection>

      <PanelSection title="项目上下文" icon={Cpu}>
        {currentProject ? (
          <div className="space-y-1.5">
            <KeyValue k="项目" v={currentProject.name} />
            <KeyValue k="PLC" v={currentProject.plc_type} />
            <KeyValue k="TIA" v={currentProject.tia_version} />
            <KeyValue k="语言" v={currentProject.language} />
          </div>
        ) : (
          <div className="text-xs text-text-dim">未选择项目，AI 助手将不携带项目上下文</div>
        )}
      </PanelSection>

      <PanelSection title="最近对话" icon={History} defaultOpen={false}>
        {recentConvs.length > 0 ? (
          <div className="space-y-1">
            {recentConvs.map((c) => (
              <div key={c.id} className="text-2xs text-text-secondary truncate p-1 hover:bg-ide-hover rounded">
                {c.title || '未命名对话'}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-text-dim">暂无对话</div>
        )}
      </PanelSection>

      <PanelSection title="知识库引用" icon={BookOpen} defaultOpen={false}>
        {ragSources.length > 0 ? (
          <div className="space-y-1">
            {ragSources.map((src, i) => (
              <div key={src.id || src.url || i} className="text-2xs p-1.5 bg-ide-panel rounded border border-ide-border">
                <div className="text-accent font-mono truncate">#{i + 1} {src.title || src.name}</div>
                {src.snippet && <div className="text-text-dim mt-0.5 line-clamp-2">{src.snippet}</div>}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-text-dim">当前对话未引用知识库</div>
        )}
      </PanelSection>
    </>
  )
}

// D-3：梯形图 Inspector — 最近 ladder 消息统计 + Network 列表 + 导出格式
function LadderInspector({ currentProject, messages }) {
  const lastLadder = findLastMessageByType(messages, 'ladder')
  const structured = lastLadder?.structured
  const networks = structured?.networks || []
  const variables = structured?.variables || []

  return (
    <>
      <PanelSection title="梯形图概览" icon={Zap}>
        {lastLadder ? (
          <div className="space-y-1.5">
            <KeyValue k="标题" v={lastLadder.title} mono={false} />
            <KeyValue k="Networks" v={networks.length} />
            <KeyValue k="变量数" v={variables.length} />
            <KeyValue k="模式" v={lastLadder.mode} />
          </div>
        ) : (
          <div className="text-xs text-text-dim">尚未生成梯形图</div>
        )}
      </PanelSection>

      <PanelSection title="Network 列表" icon={ListTree} defaultOpen={false}>
        {networks.length > 0 ? (
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {networks.map((n, i) => (
              <div key={n.number || i} className="text-2xs p-1.5 bg-ide-panel rounded border border-ide-border">
                <div className="flex items-center gap-1">
                  <span className="font-mono text-accent">N{n.number}</span>
                  <span className="text-text-primary truncate flex-1">{n.title}</span>
                </div>
                {n.comment && <div className="text-text-dim mt-0.5 truncate">// {n.comment}</div>}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-text-dim">无 Network</div>
        )}
      </PanelSection>

      <PanelSection title="导出格式" icon={FileText} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div><span className="text-accent font-mono">SCL</span> — 结构化文本</div>
          <div><span className="text-accent font-mono">XML</span> — TIA Portal 导入</div>
          <div><span className="text-accent font-mono">CSV</span> — 变量表</div>
          <div><span className="text-accent font-mono">HMI</span> — 人机界面变量</div>
        </div>
      </PanelSection>

      <PanelSection title="PLC 规范" icon={Cpu} defaultOpen={false}>
        <div className="space-y-1.5">
          <KeyValue k="PLC 类型" v={currentProject?.plc_type || 'S7-1200'} />
          <KeyValue k="TIA 版本" v={currentProject?.tia_version || 'V18'} />
        </div>
      </PanelSection>
    </>
  )
}

// D-3：IO 表 Inspector — 最近 io-table 消息统计 + 地址范围 + 分类
function IoTableInspector({ currentProject, messages }) {
  const lastIo = findLastMessageByType(messages, 'io-table')
  const parseContent = (c) => {
    if (!c) return {}
    if (typeof c === 'string') { try { return JSON.parse(c) } catch { return {} } }
    return c
  }
  const data = parseContent(lastIo?.content)
  const rows = data.rows || data.io || data.devices || []

  return (
    <>
      <PanelSection title="IO 表概览" icon={Table2}>
        {rows.length > 0 ? (
          <div className="space-y-1.5">
            <KeyValue k="设备数" v={rows.length} />
            <KeyValue k="输入点" v={rows.filter(r => r.direction === 'input' || r.type === 'I').length} />
            <KeyValue k="输出点" v={rows.filter(r => r.direction === 'output' || r.type === 'Q').length} />
          </div>
        ) : (
          <div className="text-xs text-text-dim">尚未生成 IO 表</div>
        )}
      </PanelSection>

      <PanelSection title="地址范围" icon={ListTree} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div><span className="text-accent font-mono">I0.0 ~ I0.7</span> 输入区</div>
          <div><span className="text-accent font-mono">Q0.0 ~ Q0.7</span> 输出区</div>
          <div><span className="text-accent font-mono">M0.0 ~ M14.7</span> 标志位</div>
          <div><span className="text-accent font-mono">T0 ~ T9</span> 定时器</div>
          <div><span className="text-accent font-mono">C0 ~ C9</span> 计数器</div>
        </div>
      </PanelSection>

      <PanelSection title="校验" icon={AlertCircle} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div>· 地址冲突检测</div>
          <div>· 重复分配检测</div>
          <div>· 类型匹配校验</div>
        </div>
      </PanelSection>
    </>
  )
}

// D-3：程序解析 Inspector — 最近 code 消息统计 + 块类型
function ParseInspector({ currentProject, messages }) {
  const lastCode = findLastMessageByType(messages, 'code')
  return (
    <>
      <PanelSection title="解析概览" icon={FileSearch}>
        {lastCode ? (
          <div className="space-y-1.5">
            <KeyValue k="语言" v={currentProject?.language || 'SCL'} />
            <KeyValue k="状态" v="已解析" />
          </div>
        ) : (
          <div className="text-xs text-text-dim">尚未解析程序</div>
        )}
      </PanelSection>

      <PanelSection title="块类型" icon={ListTree} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div><span className="text-accent font-mono">OB</span> 组织块（主循环/中断）</div>
          <div><span className="text-accent font-mono">FB</span> 功能块（带背景 DB）</div>
          <div><span className="text-accent font-mono">FC</span> 功能（无背景）</div>
          <div><span className="text-accent font-mono">DB</span> 数据块</div>
        </div>
      </PanelSection>

      <PanelSection title="分析" icon={Code2} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div>· 语法检查</div>
          <div>· 变量引用分析</div>
          <div>· 块调用关系</div>
        </div>
      </PanelSection>
    </>
  )
}

// D-3：故障诊断 Inspector — 最近 warning/error + 排查步骤
function DiagnoseInspector({ messages }) {
  const warnings = messages.filter(m => m.type === 'warning' || m.error)
  const lastWarn = warnings[warnings.length - 1]

  return (
    <>
      <PanelSection title="诊断概览" icon={AlertTriangle}>
        {lastWarn ? (
          <div className="space-y-1.5">
            <KeyValue k="告警数" v={warnings.length} />
            <KeyValue k="最近" v={lastWarn.content?.slice(0, 30) + '...'} mono={false} />
          </div>
        ) : (
          <div className="text-xs text-text-dim">暂无告警</div>
        )}
      </PanelSection>

      <PanelSection title="排查步骤" icon={ListTree} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div>1. 检查 PLC 电源与连接</div>
          <div>2. 验证 IO 信号</div>
          <div>3. 查看诊断缓冲区</div>
          <div>4. 分析程序逻辑</div>
          <div>5. 检查网络通信</div>
        </div>
      </PanelSection>

      <PanelSection title="设备状态" icon={Cpu} defaultOpen={false}>
        <div className="text-2xs text-text-dim">待接入 PLC 状态 API</div>
      </PanelSection>
    </>
  )
}

// D-3：编排 Inspector — 编排说明 + 工具数
function OrchestratorInspector() {
  return (
    <>
      <PanelSection title="编排概览" icon={Server}>
        <div className="space-y-1.5">
          <KeyValue k="服务器" v="orchestrator" />
          <KeyValue k="协议" v="MCP stdio" />
          <KeyValue k="状态" v="运行中" />
        </div>
      </PanelSection>

      <PanelSection title="工作流" icon={ListTree} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div>· P3 流水线（5 步）</div>
          <div>· TIA 工程态流水线</div>
          <div>· 运行态控制闭环</div>
        </div>
      </PanelSection>

      <PanelSection title="Agent" icon={Bot} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div>· Team Lead（调度）</div>
          <div>· Developer（实现）</div>
          <div>· Reviewer（审查）</div>
          <div>· Researcher（调研）</div>
        </div>
      </PanelSection>
    </>
  )
}

// D-3：变量分析 Inspector — 最近 variables 消息统计 + 命名规范
function VariablesInspector({ currentProject, messages }) {
  const lastVars = findLastMessageByType(messages, 'variables')
  const parseContent = (c) => {
    if (!c) return {}
    if (typeof c === 'string') { try { return JSON.parse(c) } catch { return {} } }
    return c
  }
  const data = parseContent(lastVars?.content)
  const vars = data.variables || data.rows || data.vars || []

  return (
    <>
      <PanelSection title="变量概览" icon={Variable}>
        {vars.length > 0 ? (
          <div className="space-y-1.5">
            <KeyValue k="变量数" v={vars.length} />
            <KeyValue k="Bool" v={vars.filter(v => v.data_type === 'Bool').length} />
            <KeyValue k="Int" v={vars.filter(v => v.data_type === 'Int').length} />
            <KeyValue k="Real" v={vars.filter(v => v.data_type === 'Real').length} />
          </div>
        ) : (
          <div className="text-xs text-text-dim">尚未分析变量</div>
        )}
      </PanelSection>

      <PanelSection title="命名规范" icon={ListTree} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div>· <span className="text-accent font-mono">bXxx</span> — Bool</div>
          <div>· <span className="text-accent font-mono">iXxx</span> — Int</div>
          <div>· <span className="text-accent font-mono">rXxx</span> — Real</div>
          <div>· <span className="text-accent font-mono">sXxx</span> — String</div>
        </div>
      </PanelSection>

      <PanelSection title="地址分配" icon={Cpu} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div>· M0.0 ~ M14.7 — 标志位</div>
          <div>· MW20 ~ MW40 — Int</div>
          <div>· MD60 ~ MD100 — Real</div>
        </div>
      </PanelSection>
    </>
  )
}

// D-3：设置 Inspector — 当前项目配置摘要
function SettingsInspector({ currentProject }) {
  return (
    <>
      <PanelSection title="项目配置" icon={SettingsIcon}>
        {currentProject ? (
          <div className="space-y-1.5">
            <KeyValue k="项目名" v={currentProject.name} />
            <KeyValue k="PLC" v={currentProject.plc_type} />
            <KeyValue k="TIA" v={currentProject.tia_version} />
            <KeyValue k="语言" v={currentProject.language} />
          </div>
        ) : (
          <div className="text-xs text-text-dim">未选择项目</div>
        )}
      </PanelSection>

      <PanelSection title="API 配置" icon={Server} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div>· API_BASE 环境变量优先</div>
          <div>· DEV 模式走 vite proxy</div>
          <div>· 生产模式 VITE_API_BASE</div>
        </div>
      </PanelSection>

      <PanelSection title="快捷键" icon={Code2} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div><span className="text-accent font-mono">Ctrl+B</span> — 切换侧栏</div>
          <div><span className="text-accent font-mono">Ctrl+J</span> — 切换底部面板</div>
          <div><span className="text-accent font-mono">Ctrl+`</span> — 切换 Inspector</div>
          <div><span className="text-accent font-mono">Esc</span> — 关闭弹窗</div>
        </div>
      </PanelSection>
    </>
  )
}

const INSPECTOR_MAP = {
  welcome: { component: WelcomeInspector, isCustom: true },
  chat: { component: ChatInspector, isCustom: true },
  ladder: { component: LadderInspector, isCustom: true },
  'io-table': { component: IoTableInspector, isCustom: true },
  parse: { component: ParseInspector, isCustom: true },
  diagnose: { component: DiagnoseInspector, isCustom: true },
  orchestrator: { component: OrchestratorInspector, isCustom: true },
  variables: { component: VariablesInspector, isCustom: true },
  settings: { component: SettingsInspector, isCustom: true },
  robot: { icon: Cpu },
}

export default function InspectorPanel({ addLog, currentProject, activeTab, messages = [], selectedModel, conversations = [] }) {
  const inspector = INSPECTOR_MAP[activeTab] || INSPECTOR_MAP.welcome

  return (
    <aside className="w-full bg-ide-sidebar border-l border-ide-border flex flex-col shrink-0 overflow-hidden h-full">
      <div className="flex-1 overflow-y-auto">
        {inspector.isCustom ? (
          <inspector.component
            addLog={addLog}
            currentProject={currentProject}
            messages={messages}
            selectedModel={selectedModel}
            conversations={conversations}
          />
        ) : (
          <div className="p-3">
            <div className="flex items-center gap-2 px-2 py-2 text-2xs font-semibold uppercase tracking-wider text-text-dim border-b border-ide-border">
              {inspector.icon && <inspector.icon size={13} />}
              <span>Inspector</span>
            </div>
            <div className="p-3">
              <EmptyState icon={Inbox} description="未接入" />
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}
