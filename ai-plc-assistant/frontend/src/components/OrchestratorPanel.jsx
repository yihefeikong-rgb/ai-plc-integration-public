import { useState, useEffect, useCallback } from 'react'
import {
  RefreshCw, Play, Server, Wrench, GitBranch,
  CheckCircle2, XCircle, Loader2, AlertCircle,
  ChevronDown, ChevronRight, Activity, Clock,
} from 'lucide-react'
import { API_BASE } from '../api'

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

function formatUptime(seconds) {
  if (seconds == null) return '--'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m`
  return `${Math.floor(seconds)}s`
}

/* ── 状态卡片 ── */
function StatCard({ icon: Icon, label, value, color }) {
  const dotColor = color === 'green' ? 'bg-status-ok'
    : color === 'red' ? 'bg-status-error'
    : 'bg-accent'
  return (
    <div className="bg-ide-sidebar border border-ide-border rounded p-4 flex items-center gap-3">
      <div className="relative">
        <Icon size={20} className="text-text-secondary" />
        <span className={`absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full ${dotColor}`} />
      </div>
      <div>
        <div className="text-lg font-semibold text-text-bright">{value}</div>
        <div className="text-2xs text-text-dim">{label}</div>
      </div>
    </div>
  )
}

/* ── 工作流执行输入弹窗 ── */
function RunDialog({ name, onRun, onCancel }) {
  const [input, setInput] = useState('{}')
  const [invalid, setInvalid] = useState(false)

  const handleChange = (v) => {
    setInput(v)
    try { JSON.parse(v); setInvalid(false) } catch { setInvalid(true) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onCancel}>
      <div className="bg-ide-sidebar border border-ide-border rounded shadow-lg w-[400px] p-4" onClick={e => e.stopPropagation()}>
        <h3 className="text-sm font-semibold text-text-bright mb-3">
          运行工作流: <span className="text-accent font-mono">{name}</span>
        </h3>
        <label className="text-2xs text-text-dim mb-1 block">输入参数 (JSON)</label>
        <textarea
          value={input}
          onChange={e => handleChange(e.target.value)}
          rows={6}
          spellCheck={false}
          className={`w-full bg-ide-bg border rounded p-2 text-xs text-text-primary font-mono focus:outline-none resize-none ${
            invalid ? 'border-status-error/50' : 'border-ide-border focus:border-accent/50'
          }`}
        />
        {invalid && <div className="text-2xs text-status-error mt-1">JSON 格式无效</div>}
        <div className="flex justify-end gap-2 mt-3">
          <button onClick={onCancel}
            className="px-3 py-1.5 text-xs text-text-secondary hover:text-text-primary border border-ide-border rounded hover:bg-ide-hover transition-colors">
            取消
          </button>
          <button onClick={() => onRun(name, JSON.parse(input))} disabled={invalid}
            className="px-3 py-1.5 text-xs text-white bg-accent rounded hover:bg-accent-hover transition-colors flex items-center gap-1.5 disabled:opacity-40">
            <Play size={12} /> 运行
          </button>
        </div>
      </div>
    </div>
  )
}

/* ── 工作流步骤行 ── */
function StepRow({ step, index }) {
  const ok = step.ok !== false
  return (
    <div className="flex items-center gap-2 py-1 text-xs">
      <span className="text-text-dim w-5 text-right shrink-0">{index + 1}.</span>
      {ok
        ? <CheckCircle2 size={13} className="text-status-ok shrink-0" />
        : <XCircle size={13} className="text-status-error shrink-0" />}
      <span className="text-text-secondary font-mono truncate flex-1">
        {step.server && <span className="text-text-dim">{step.server}.</span>}
        {step.tool || step.name || 'unknown'}
      </span>
      {step.duration_ms != null && (
        <span className="text-text-dim text-2xs flex items-center gap-1 shrink-0">
          <Clock size={10} />{step.duration_ms}ms
        </span>
      )}
    </div>
  )
}

/* ── 工具分组列表 ── */
function ToolGroup({ server, tools }) {
  const [open, setOpen] = useState(true)
  return (
    <div>
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-1.5 px-3 py-1.5 text-2xs font-semibold uppercase tracking-wider text-text-dim hover:text-text-secondary">
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <Server size={12} />
        <span>{server}</span>
        <span className="ml-auto text-text-dim font-normal">{tools.length}</span>
      </button>
      {open && tools.map(t => (
        <div key={t.name} className="flex items-center gap-2 pl-7 pr-3 py-1 text-xs text-text-secondary hover:bg-ide-hover">
          <Wrench size={12} className="text-text-dim shrink-0" />
          <span className="font-mono truncate flex-1">{t.name}</span>
          {t.category && (
            <span className="text-2xs px-1.5 py-0.5 rounded bg-ide-bg text-text-dim border border-ide-border shrink-0">
              {t.category}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

/* ── 主组件 ── */
export default function OrchestratorPanel() {
  const [workflows, setWorkflows] = useState([])
  const [tools, setTools] = useState([])
  const [servers, setServers] = useState([])
  const [monitor, setMonitor] = useState(null)
  const [lastResult, setLastResult] = useState(null)
  const [running, setRunning] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [runDialog, setRunDialog] = useState(null)

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [wf, tl, sv, mn] = await Promise.all([
        apiGet('/orchestrator/workflows').catch(() => ({ workflows: [] })),
        apiGet('/orchestrator/tools').catch(() => ({ tools: [] })),
        apiGet('/orchestrator/servers').catch(() => ({ servers: [] })),
        apiGet('/orchestrator/monitor').catch(() => null),
      ])
      setWorkflows(wf.workflows || [])
      setTools(tl.tools || [])
      setServers(sv.servers || [])
      setMonitor(mn)
    } catch (e) {
      setError(e.message)
    }
    setLoading(false)
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  const handleRun = async (name, input) => {
    setRunDialog(null)
    setRunning(true)
    setError(null)
    try {
      const result = await apiPost(`/orchestrator/workflows/${encodeURIComponent(name)}/run`, { input })
      setLastResult({ workflow: name, ...result })
    } catch (e) {
      setLastResult({ workflow: name, error: e.message, steps: [] })
    }
    setRunning(false)
  }

  // 按服务器分组工具
  const toolsByServer = tools.reduce((acc, t) => {
    const key = t.server || 'unknown'
    ;(acc[key] = acc[key] || []).push(t)
    return acc
  }, {})

  const connectedServers = servers.filter(s => s.tool_count > 0).length
  const serverColor = connectedServers > 0 ? 'green' : 'red'

  return (
    <div className="flex-1 overflow-y-auto p-6 max-w-6xl mx-auto">
      {/* 顶栏 */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <Activity size={18} className="text-accent" />
          <h1 className="text-lg font-semibold text-text-bright">编排层监控</h1>
        </div>
        <button onClick={fetchAll} disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-text-secondary border border-ide-border rounded hover:text-text-primary hover:bg-ide-hover transition-colors disabled:opacity-50">
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          刷新
        </button>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="flex items-center gap-2 mb-4 px-3 py-2 bg-status-error/10 border border-status-error/30 rounded text-xs text-status-error">
          <AlertCircle size={14} className="shrink-0" />
          {error}
        </div>
      )}

      {/* 首次加载骨架 */}
      {loading && !monitor ? (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            {[0, 1, 2].map(i => (
              <div key={i} className="bg-ide-sidebar border border-ide-border rounded p-4 animate-pulse">
                <div className="h-5 bg-ide-bg rounded w-16 mb-2" />
                <div className="h-3 bg-ide-bg rounded w-24" />
              </div>
            ))}
          </div>
          <div className="h-64 bg-ide-sidebar border border-ide-border rounded animate-pulse" />
        </div>
      ) : (
        <>
          {/* 状态卡片 */}
          <div className="grid grid-cols-3 gap-4 mb-5">
            <StatCard icon={Server} label="已连接服务器" value={`${connectedServers} / ${servers.length}`} color={serverColor} />
            <StatCard icon={Wrench} label="注册工具" value={tools.length} color="accent" />
            <StatCard icon={GitBranch} label="可用工作流" value={workflows.length} color="accent" />
          </div>

          {/* 执行中提示 */}
          {running && (
            <div className="flex items-center gap-2 mb-4 px-3 py-2 bg-accent/10 border border-accent/30 rounded text-xs text-accent">
              <Loader2 size={14} className="animate-spin shrink-0" />
              工作流执行中...
            </div>
          )}

          {/* 主体：左工作流 + 右工具 */}
          <div className="grid grid-cols-2 gap-4 mb-5">
            {/* 工作流列表 */}
            <div className="bg-ide-sidebar border border-ide-border rounded overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-2.5 border-b border-ide-border">
                <GitBranch size={14} className="text-text-dim" />
                <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">工作流</span>
                <span className="ml-auto text-2xs text-text-dim">{workflows.length}</span>
              </div>
              <div className="divide-y divide-ide-border max-h-[320px] overflow-y-auto">
                {workflows.length === 0 ? (
                  <div className="px-4 py-6 text-center text-text-dim text-xs">暂无可用工作流</div>
                ) : (
                  workflows.map(name => (
                    <div key={name} className="flex items-center gap-2 px-4 py-2.5 hover:bg-ide-hover">
                      <span className="text-xs text-text-primary font-mono truncate flex-1">{name}</span>
                      <button
                        onClick={() => setRunDialog(name)}
                        disabled={running}
                        className="shrink-0 flex items-center gap-1 px-2 py-1 text-2xs text-accent border border-accent/30 rounded hover:bg-accent/10 transition-colors disabled:opacity-40"
                      >
                        <Play size={10} /> 运行
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* 工具列表 */}
            <div className="bg-ide-sidebar border border-ide-border rounded overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-2.5 border-b border-ide-border">
                <Wrench size={14} className="text-text-dim" />
                <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">工具</span>
                <span className="ml-auto text-2xs text-text-dim">{tools.length}</span>
              </div>
              <div className="max-h-[320px] overflow-y-auto pb-1">
                {tools.length === 0 ? (
                  <div className="px-4 py-6 text-center text-text-dim text-xs">暂无注册工具</div>
                ) : (
                  Object.entries(toolsByServer).map(([server, st]) => (
                    <ToolGroup key={server} server={server} tools={st} />
                  ))
                )}
              </div>
            </div>
          </div>

          {/* 执行结果 */}
          {lastResult && (
            <div className="bg-ide-sidebar border border-ide-border rounded overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-2.5 border-b border-ide-border">
                {lastResult.error
                  ? <XCircle size={14} className="text-status-error" />
                  : <CheckCircle2 size={14} className="text-status-ok" />}
                <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">执行结果</span>
                <span className="text-2xs text-text-dim ml-2 font-mono">{lastResult.workflow}</span>
                <span className={`ml-auto text-2xs font-medium ${lastResult.error ? 'text-status-error' : 'text-status-ok'}`}>
                  {lastResult.error ? '失败' : '成功'}
                </span>
              </div>
              <div className="px-4 py-2 max-h-[240px] overflow-y-auto">
                {lastResult.error && (
                  <div className="flex items-center gap-2 py-1 text-xs text-status-error mb-1">
                    <AlertCircle size={13} className="shrink-0" />
                    <span className="truncate">{lastResult.error}</span>
                  </div>
                )}
                {(lastResult.steps || []).length === 0 && !lastResult.error ? (
                  <div className="py-3 text-center text-text-dim text-xs">无步骤信息</div>
                ) : (
                  (lastResult.steps || []).map((step, i) => (
                    <StepRow key={i} step={step} index={i} />
                  ))
                )}
              </div>
            </div>
          )}

          {/* 底部监控信息 */}
          {monitor && (
            <div className="mt-4 flex items-center gap-4 text-2xs text-text-dim">
              <span className="flex items-center gap-1">
                <Clock size={11} />
                运行时间: {formatUptime(monitor.uptime_seconds)}
              </span>
              {monitor.call_counts && (
                <span>调用次数: {Object.values(monitor.call_counts).reduce((a, b) => a + b, 0)}</span>
              )}
            </div>
          )}
        </>
      )}

      {/* 运行弹窗 */}
      {runDialog && (
        <RunDialog
          name={runDialog}
          onRun={handleRun}
          onCancel={() => setRunDialog(null)}
        />
      )}
    </div>
  )
}
