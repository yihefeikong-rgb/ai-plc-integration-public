import { useState, useEffect } from 'react'
import {
  Code2, FileSearch, Search, FolderInput,
  Clock, ArrowRight, FolderOpen, Plus, MessageSquare,
  ChevronRight, Upload, FileCode2, Table2, Variable, CheckCircle2,
} from 'lucide-react'
import {
  listProjects, listConversations, healthCheck, orchestratorHealth, listServers,
} from '../api'
import { SAFETY_LEVELS, DEFAULT_SAFETY_LEVEL } from '../platform/safetyLevels'

/**
 * Dashboard — 工程工作台总览（Batch 5 重构）
 *
 * 5 区域（主计划 §8.2）：
 * 1. 全局状态：后端/PLC/TIA/PLCSIM/MCP/当前工程/安全模式（真实状态，不伪造）
 * 2. 快捷操作：新建项目/导入项目/新建对话/生成梯形图/生成 IO 表
 * 3. 工作流程：描述需求→生成 IO 表→生成变量→生成梯形图→审查逻辑→导出程序→导入 TIA Portal
 * 4. 继续工作：当前项目信息 + 最近对话
 * 5. 最近活动：最近项目/对话/生成任务/导出/错误/告警
 */

const WORKFLOW_STEPS = [
  { id: 1, label: '描述需求', icon: MessageSquare },
  { id: 2, label: '生成 IO 表', icon: Table2 },
  { id: 3, label: '生成变量', icon: Variable },
  { id: 4, label: '生成梯形图', icon: Code2 },
  { id: 5, label: '审查逻辑', icon: CheckCircle2 },
  { id: 6, label: '导出程序', icon: FileCode2 },
  { id: 7, label: '导入 TIA Portal', icon: Upload },
]

const QUICK_ACTIONS = [
  { id: 'new-project', icon: Plus, label: '新建项目', desc: '创建新的 PLC 工程' },
  { id: 'import-project', icon: FolderInput, label: '导入项目', desc: '导入 .ap18/.ap19 工程' },
  { id: 'new-chat', icon: MessageSquare, label: '新建对话', desc: '开始 AI 对话' },
  { id: 'ladder', icon: Code2, label: '生成梯形图', desc: '自然语言生成 PLC 程序' },
  { id: 'io-table', icon: Search, label: '生成 IO 表', desc: '描述设备生成 IO 表' },
]

// F-067 修复：复用 GlobalStatusBar 的 matchServers 逻辑推断 PLC/TIA/PLCSIM 连接状态
function matchServers(servers) {
  const result = { plc: false, tia: false, plcsim: false }
  if (!Array.isArray(servers)) return result
  for (const s of servers) {
    const name = (s.name || s.id || '').toLowerCase()
    const status = s.status || s.state || ''
    const connected = status === 'connected' || status === 'running' || status === 'ok' || s.connected === true
    if (!connected) continue
    if (/plcsim|plc.sim/i.test(name)) result.plcsim = true
    else if (/tia/i.test(name)) result.tia = true
    else if (/plc|s7/i.test(name)) result.plc = true
  }
  return result
}

// F-068 修复：从 localStorage 读取安全等级，与 GlobalStatusBar 切换同步
const SAFETY_LEVELS_LIST = [
  SAFETY_LEVELS.LEVEL_0_READONLY,
  SAFETY_LEVELS.LEVEL_1_LOCAL_WRITE,
  SAFETY_LEVELS.LEVEL_2_PROJECT_MODIFY,
  SAFETY_LEVELS.LEVEL_3_DEVICE_CONTROL,
]
const SAFETY_STORAGE_KEY = 'ai-plc:safety-level'

function loadSafetyLevel() {
  try {
    const saved = localStorage.getItem(SAFETY_STORAGE_KEY)
    if (saved) {
      const found = SAFETY_LEVELS_LIST.find((l) => l.id === saved)
      if (found) return found
    }
  } catch (e) {
    // F-070 修复：localStorage 读取失败记录警告
    console.warn('[Dashboard] localStorage.getItem(safety-level) 失败:', e?.message)
  }
  return DEFAULT_SAFETY_LEVEL
}

function timeAgo(ts) {
  if (!ts) return ''
  const diff = (Date.now() / 1000) - ts
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  if (diff < 604800) return `${Math.floor(diff / 86400)}天前`
  return new Date(ts * 1000).toLocaleDateString()
}

function StatusRow({ label, value, tone = 'neutral' }) {
  // tone: ok / offline / neutral / readonly / warning / danger
  // F-068a 修复：补 warning/danger 桶位，与 safetyLevels.tone 对齐（tailwind 色板为 warn/danger）
  const toneClass = {
    ok: 'text-status-ok',
    offline: 'text-status-offline',
    neutral: 'text-text-secondary',
    readonly: 'text-status-readonly',
    warning: 'text-status-warn',
    danger: 'text-status-danger',
  }[tone] || 'text-text-secondary'
  return (
    <div className="flex items-center justify-between py-1 text-xs">
      <span className="text-text-dim">{label}</span>
      <span className={`font-mono ${toneClass}`}>{value}</span>
    </div>
  )
}

function SectionCard({ title, children, action }) {
  return (
    <section className="bg-ide-panel border border-ide-border rounded flex flex-col">
      <header className="flex items-center justify-between px-3 py-2 border-b border-ide-border">
        <h2 className="text-2xs font-semibold text-text-secondary uppercase tracking-wider">{title}</h2>
        {action}
      </header>
      <div className="flex-1 p-3">{children}</div>
    </section>
  )
}

export default function Dashboard({
  onOpenTab,
  onCreateProject,
  onImportProject,
  onNewConversation,
  currentProject,
  conversations,
  onSwitchConversation,
}) {
  const [projects, setProjects] = useState([])
  const [recentConversations, setRecentConversations] = useState([])
  const [health, setHealth] = useState(null)
  const [orchHealth, setOrchHealth] = useState(null)
  // F-067/F-068 修复：真实 PLC/TIA/PLCSIM 状态 + localStorage 安全等级
  const [serverMatches, setServerMatches] = useState({ plc: false, tia: false, plcsim: false })
  const [safetyLevel, setSafetyLevel] = useState(loadSafetyLevel)

  useEffect(() => {
    listProjects(5).then((d) => setProjects(d.projects || [])).catch(() => {})
    if (!conversations || conversations.length === 0) {
      listConversations(5).then((d) => setRecentConversations(d.conversations || [])).catch(() => {})
    }
    healthCheck().then(setHealth).catch(() => setHealth(null))
    orchestratorHealth().then(setOrchHealth).catch(() => setOrchHealth(null))
    // F-067：复用 GlobalStatusBar 的 matchServers 推断 PLC/TIA/PLCSIM
    listServers()
      .then((s) => setServerMatches(matchServers(s?.servers || s)))
      .catch(() => setServerMatches({ plc: false, tia: false, plcsim: false }))
  }, [conversations])

  // F-068：监听 localStorage 安全等级变化（与 GlobalStatusBar 切换同步）
  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === SAFETY_STORAGE_KEY) setSafetyLevel(loadSafetyLevel())
    }
    const onFocus = () => setSafetyLevel(loadSafetyLevel())
    window.addEventListener('storage', onStorage)
    window.addEventListener('focus', onFocus)
    return () => {
      window.removeEventListener('storage', onStorage)
      window.removeEventListener('focus', onFocus)
    }
  }, [])

  const convs = conversations || recentConversations
  const mcpConnected = orchHealth?.servers_connected > 0

  const handleQuickAction = (id) => {
    if (id === 'new-project') onCreateProject?.()
    else if (id === 'import-project') onImportProject?.()
    else if (id === 'new-chat') onNewConversation?.()
    else onOpenTab?.(id)
  }

  const handleConvClick = (c) => {
    onSwitchConversation?.(c.id)
  }

  return (
    <div className="flex-1 overflow-y-auto bg-ide-bg">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-lg font-semibold text-text-bright mb-1">工程工作台</h1>
          <p className="text-xs text-text-dim">AI PLC Assistant v1.0 — 工业自动化编程工作台</p>
        </div>

        {/* Row 1: 全局状态 + 快捷操作 */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          <SectionCard title="全局状态">
            <StatusRow label="后端服务" value={health ? '在线' : '未连接'} tone={health ? 'ok' : 'offline'} />
            <StatusRow label="PLC" value={serverMatches.plc ? '已连接' : '未连接'} tone={serverMatches.plc ? 'ok' : 'offline'} />
            <StatusRow label="TIA Portal" value={serverMatches.tia ? '已启动' : '未启动'} tone={serverMatches.tia ? 'ok' : 'offline'} />
            <StatusRow label="PLCSIM" value={serverMatches.plcsim ? '已启用' : '未启用'} tone={serverMatches.plcsim ? 'ok' : 'neutral'} />
            <StatusRow
              label="MCP Server"
              value={mcpConnected ? `${orchHealth.servers_connected} 已连` : '未连接'}
              tone={mcpConnected ? 'ok' : 'offline'}
            />
            <StatusRow
              label="当前工程"
              value={currentProject?.name || '未选择'}
              tone={currentProject ? 'ok' : 'neutral'}
            />
            <StatusRow label="安全模式" value={safetyLevel.label} tone={safetyLevel.tone} />
          </SectionCard>

          <SectionCard title="快捷操作">
            <div className="grid grid-cols-1 gap-1">
              {QUICK_ACTIONS.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => handleQuickAction(a.id)}
                  className="flex items-center gap-3 px-2.5 py-2 rounded hover:bg-ide-hover text-left transition-colors group"
                >
                  <a.icon size={16} className="text-accent shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-text-primary font-medium">{a.label}</div>
                    <div className="text-2xs text-text-dim">{a.desc}</div>
                  </div>
                  <ChevronRight size={14} className="text-text-dim opacity-0 group-hover:opacity-100" />
                </button>
              ))}
            </div>
          </SectionCard>
        </div>

        {/* Row 2: 工作流程 */}
        <SectionCard title="工作流程">
          <div className="flex items-center gap-1 overflow-x-auto">
            {WORKFLOW_STEPS.map((step, i) => (
              <div key={step.id} className="flex items-center gap-1 shrink-0">
                <div className="flex items-center gap-2 px-3 py-2 bg-ide-sidebar rounded border border-ide-border">
                  <span className="text-2xs text-text-dim font-mono">{step.id}</span>
                  <step.icon size={14} className="text-accent" />
                  <span className="text-xs text-text-secondary whitespace-nowrap">{step.label}</span>
                </div>
                {i < WORKFLOW_STEPS.length - 1 && (
                  <ChevronRight size={14} className="text-text-dim shrink-0" />
                )}
              </div>
            ))}
          </div>
        </SectionCard>

        {/* Row 3: 继续工作 + 最近活动 */}
        <div className="grid grid-cols-2 gap-4 mt-4">
          <SectionCard title="继续工作">
            {currentProject ? (
              <>
                <div className="mb-3 pb-3 border-b border-ide-border">
                  <div className="text-sm text-text-primary font-medium mb-2">{currentProject.name}</div>
                  <StatusRow label="PLC 型号" value={currentProject.plc_type || '-'} />
                  <StatusRow label="TIA 版本" value={currentProject.tia_version || '-'} />
                  <StatusRow label="编程语言" value={currentProject.language || '-'} />
                </div>
                <div className="text-2xs text-text-dim uppercase tracking-wider mb-2">最近对话</div>
                {convs.length > 0 ? (
                  convs.slice(0, 3).map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => handleConvClick(c)}
                      className="w-full flex items-center gap-2 py-1.5 px-1.5 rounded hover:bg-ide-hover text-left transition-colors"
                    >
                      <MessageSquare size={12} className="text-text-dim shrink-0" />
                      <span className="text-xs text-text-secondary flex-1 truncate">{c.title || '无标题对话'}</span>
                      <span className="text-2xs text-text-dim shrink-0">{timeAgo(c.updated_at)}</span>
                    </button>
                  ))
                ) : (
                  <div className="text-2xs text-text-dim py-2">暂无对话</div>
                )}
              </>
            ) : (
              <div className="py-6 text-center">
                <FolderOpen size={24} className="text-text-dim mx-auto mb-2 opacity-50" />
                <div className="text-xs text-text-dim mb-3">未选择项目</div>
                <button
                  type="button"
                  onClick={onCreateProject}
                  className="px-3 py-1.5 bg-accent text-white rounded text-xs hover:bg-accent-hover transition-colors"
                >
                  新建项目
                </button>
              </div>
            )}
          </SectionCard>

          <SectionCard title="最近活动">
            <div className="text-2xs text-text-dim uppercase tracking-wider mb-2">最近项目</div>
            {projects.length > 0 ? (
              <div className="space-y-0.5 mb-3">
                {projects.slice(0, 3).map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => onOpenTab?.('project', p)}
                    className="w-full flex items-center gap-2 py-1.5 px-1.5 rounded hover:bg-ide-hover text-left transition-colors group"
                  >
                    <FolderOpen size={12} className="text-accent shrink-0" />
                    <span className="text-xs text-text-secondary flex-1 truncate">{p.name}</span>
                    <span className="text-2xs text-text-dim shrink-0">{timeAgo(p.last_opened_at)}</span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="text-2xs text-text-dim py-2 mb-3">暂无项目</div>
            )}

            <div className="text-2xs text-text-dim uppercase tracking-wider mb-2">最近对话</div>
            {convs.length > 0 ? (
              <div className="space-y-0.5">
                {convs.slice(0, 3).map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => handleConvClick(c)}
                    className="w-full flex items-center gap-2 py-1.5 px-1.5 rounded hover:bg-ide-hover text-left transition-colors"
                  >
                    <MessageSquare size={12} className="text-text-dim shrink-0" />
                    <span className="text-xs text-text-secondary flex-1 truncate">{c.title || '无标题对话'}</span>
                    <span className="text-2xs text-text-dim shrink-0">{timeAgo(c.updated_at)}</span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="text-2xs text-text-dim py-2">暂无对话</div>
            )}

            <div className="mt-3 pt-3 border-t border-ide-border">
              <div className="text-2xs text-text-dim uppercase tracking-wider mb-1">其他活动</div>
              <div className="text-2xs text-text-dim py-1">
                生成任务 / 导出 / 错误 / 告警 — 待接入
              </div>
            </div>
          </SectionCard>
        </div>
      </div>
    </div>
  )
}
