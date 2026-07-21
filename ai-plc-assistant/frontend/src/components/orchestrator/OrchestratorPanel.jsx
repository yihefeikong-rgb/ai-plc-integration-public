import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  RefreshCw, Play, Server, Wrench, GitBranch,
  CheckCircle2, XCircle, Loader2, AlertCircle,
  ChevronRight, Activity, Clock,
  Search, Plus, Trash2, Save, GripVertical, X,
  Edit3, HelpCircle,
} from 'lucide-react'
import { cn, WORKFLOW_CN, CATEGORY_CN, SERVER_CN, TOOL_CN } from './constants'
import { apiGet, apiPost, apiDelete } from './api'
import StatCard from './StatCard'
import StepResultRow from './StepResultRow'
import ToolGroup from './ToolGroup'
import RunDialog, { formatUptime } from './RunDialog'
import TutorialModal from './TutorialModal'

export default function OrchestratorPanel({ showTutorial = false, onCloseTutorial = () => {} }) {
  const [workflows, setWorkflows] = useState([])
  const [dynamicWfs, setDynamicWfs] = useState([])
  const [tools, setTools] = useState([])
  const [servers, setServers] = useState([])
  const [monitor, setMonitor] = useState(null)
  const [lastResult, setLastResult] = useState(null)
  const [running, setRunning] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [runDialog, setRunDialog] = useState(null)
  const [localTutorial, setLocalTutorial] = useState(false)
  const workflowSucceeded = lastResult?.ok === true && !lastResult?.error && (lastResult.steps || []).every(step => step.ok === true)

  // 工具搜索
  const [toolSearch, setToolSearch] = useState('')

  // 工作流编辑器
  const [editing, setEditing] = useState(null) // null | { name, steps, isNew }
  const [editorSteps, setEditorSteps] = useState([])
  const [editorName, setEditorName] = useState('')
  const [addStepOpen, setAddStepOpen] = useState(false)
  const [stepServer, setStepServer] = useState('')
  const [stepTool, setStepTool] = useState('')
  const [stepParams, setStepParams] = useState('{}')

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [wf, dyn, tl, sv, mn] = await Promise.all([
        apiGet('/orchestrator/workflows').catch(() => ({ workflows: [] })),
        apiGet('/orchestrator/workflows/dynamic').catch(() => ({ workflows: [] })),
        apiGet('/orchestrator/tools').catch(() => ({ tools: [] })),
        apiGet('/orchestrator/servers').catch(() => ({ servers: [] })),
        apiGet('/orchestrator/monitor').catch(() => null),
      ])
      setWorkflows(wf.workflows || [])
      setDynamicWfs(dyn.workflows || [])
      setTools(tl.tools || [])
      setServers(sv.servers || [])
      setMonitor(mn)
    } catch (e) { setError(e.message) }
    setLoading(false)
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  // 过滤工具
  const filteredTools = useMemo(() => {
    if (!toolSearch.trim()) return tools
    const q = toolSearch.toLowerCase()
    return tools.filter(t =>
      t.name.toLowerCase().includes(q) ||
      t.server.toLowerCase().includes(q) ||
      cn(t.name, TOOL_CN).includes(q) ||
      (t.category && cn(t.category, CATEGORY_CN).includes(q))
    )
  }, [tools, toolSearch])

  // 按服务器分组工具
  const toolsByServer = useMemo(() => {
    const acc = {}
    filteredTools.forEach(t => {
      const key = t.server || 'unknown'
      ;(acc[key] = acc[key] || []).push(t)
    })
    return acc
  }, [filteredTools])

  // 区分内置和动态工作流
  const dynamicNames = new Set(dynamicWfs.map(w => w.name))
  const builtinWorkflows = workflows.filter(w => !dynamicNames.has(w))
  const dynamicWorkflows = workflows.filter(w => dynamicNames.has(w))

  const connectedServers = servers.filter(s => s.tool_count > 0).length
  const serverColor = connectedServers > 0 ? 'green' : 'red'

  // ---- 执行工作流 ----
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

  // ---- 编辑器 ----
  const startEdit = (name, steps, isNew) => {
    setEditing({ name, isNew })
    setEditorName(name)
    setEditorSteps(steps ? [...steps] : [])
    setAddStepOpen(false)
  }

  const cancelEdit = () => {
    setEditing(null)
    setEditorSteps([])
    setEditorName('')
    setAddStepOpen(false)
  }

  const addStep = () => {
    if (!stepServer || !stepTool) return
    let params = {}
    try { params = JSON.parse(stepParams) } catch { params = {} }
    setEditorSteps(prev => [...prev, { server: stepServer, tool: stepTool, params }])
    setStepServer('')
    setStepTool('')
    setStepParams('{}')
    setAddStepOpen(false)
  }

  const removeStep = (i) => {
    setEditorSteps(prev => prev.filter((_, idx) => idx !== i))
  }

  const moveStep = (i, dir) => {
    const next = [...editorSteps]
    const target = i + dir
    if (target < 0 || target >= next.length) return
    ;[next[i], next[target]] = [next[target], next[i]]
    setEditorSteps(next)
  }

  const saveWorkflow = async () => {
    if (!editorName.trim() || editorSteps.length === 0) return
    try {
      await apiPost('/orchestrator/workflows/dynamic', { name: editorName.trim(), steps: editorSteps })
      setEditing(null)
      fetchAll()
    } catch (e) { setError(e.message) }
  }

  const deleteWorkflow = async (name) => {
    try {
      await apiDelete(`/orchestrator/workflows/dynamic/${encodeURIComponent(name)}`)
      fetchAll()
    } catch (e) { setError(e.message) }
  }

  const executeAdhoc = async () => {
    if (editorSteps.length === 0) return
    setRunning(true)
    setError(null)
    try {
      const result = await apiPost('/orchestrator/workflows/adhoc', { steps: editorSteps, input: {} })
      setLastResult({ workflow: editorName || '临时执行', ...result })
    } catch (e) {
      setLastResult({ workflow: editorName || '临时执行', error: e.message, steps: [] })
    }
    setRunning(false)
  }

  // 当前选中服务器的工具列表
  const serverTools = stepServer ? tools.filter(t => t.server === stepServer) : []

  return (
    <div className="flex-1 overflow-y-auto p-6 max-w-6xl mx-auto">
      {/* 顶栏 */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <Activity size={18} className="text-accent" />
          <h1 className="text-lg font-semibold text-text-bright">编排管理</h1>
        </div>
        <div className="flex items-center gap-2">
          {!editing && (
            <>
              <button onClick={() => setLocalTutorial(true)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-text-secondary border border-ide-border rounded hover:text-text-primary hover:bg-ide-hover transition-colors"
                title="编排管理教程">
                <HelpCircle size={13} /> 教程
              </button>
              <button onClick={() => startEdit('', [], true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-white bg-accent rounded hover:bg-accent-hover transition-colors">
                <Plus size={13} /> 新建工作流
              </button>
            </>
          )}
          <button onClick={fetchAll} disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-text-secondary border border-ide-border rounded hover:text-text-primary hover:bg-ide-hover transition-colors disabled:opacity-50">
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            刷新
          </button>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="flex items-center gap-2 mb-4 px-3 py-2 bg-status-error/10 border border-status-error/30 rounded text-xs text-status-error">
          <AlertCircle size={14} className="shrink-0" />{error}
        </div>
      )}

      {/* 加载骨架 */}
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
        </div>
      ) : (
        <>
          {/* 状态卡片 */}
          <div className="grid grid-cols-3 gap-4 mb-5">
            <StatCard icon={Server} label="已连接服务器" value={`${connectedServers} / ${servers.length}`} color={serverColor} />
            <StatCard icon={Wrench} label="注册工具" value={tools.length} color="accent" />
            <StatCard icon={GitBranch} label="可用工作流" value={workflows.length} color="accent" />
          </div>

          {running && (
            <div className="flex items-center gap-2 mb-4 px-3 py-2 bg-accent/10 border border-accent/30 rounded text-xs text-accent">
              <Loader2 size={14} className="animate-spin shrink-0" />工作流执行中...
            </div>
          )}

          {/* ======== 工作流编辑器 ======== */}
          {editing && (
            <div className="bg-ide-sidebar border border-accent/30 rounded p-4 mb-5">
              <div className="flex items-center gap-2 mb-4">
                <GitBranch size={16} className="text-accent" />
                <span className="text-sm font-semibold text-text-bright">
                  {editing.isNew ? '新建工作流' : `编辑: ${cn(editing.name, WORKFLOW_CN) || editing.name}`}
                </span>
              </div>

              {/* 名称 */}
              <div className="flex items-center gap-3 mb-4">
                <label className="text-xs text-text-dim w-16 shrink-0">名称</label>
                <input value={editorName} onChange={e => setEditorName(e.target.value)}
                  placeholder="my_workflow"
                  className="flex-1 bg-ide-bg border border-ide-border rounded px-3 py-1.5 text-xs text-text-primary font-mono outline-none focus:border-accent/50" />
              </div>

              {/* 步骤列表 */}
              <div className="mb-3">
                <div className="text-xs font-medium text-text-secondary mb-2">步骤 ({editorSteps.length})</div>
                {editorSteps.length === 0 ? (
                  <div className="text-xs text-text-dim py-3 text-center border border-dashed border-ide-border rounded">暂无步骤，点击下方"添加步骤"</div>
                ) : (
                  <div className="space-y-1">
                    {editorSteps.map((step, i) => (
                      <div key={i} className="flex items-center gap-2 bg-ide-bg border border-ide-border rounded px-3 py-2 text-xs group">
                        <GripVertical size={14} className="text-text-dim cursor-grab" />
                        <span className="text-text-dim w-5 text-right">{i + 1}.</span>
                        <span className="text-accent font-mono">{cn(step.server, SERVER_CN) || step.server}</span>
                        <span className="text-text-dim">.</span>
                        <span className="text-text-primary font-mono flex-1">{cn(step.tool, TOOL_CN)}</span>
                        <span className="text-text-dim text-2xs font-mono">{step.server}.{step.tool}</span>
                        <button onClick={() => moveStep(i, -1)} disabled={i === 0}
                          className="opacity-0 group-hover:opacity-100 text-text-dim hover:text-text-primary disabled:opacity-20">
                          <ChevronRight size={12} className="rotate-180" />
                        </button>
                        <button onClick={() => moveStep(i, 1)} disabled={i === editorSteps.length - 1}
                          className="opacity-0 group-hover:opacity-100 text-text-dim hover:text-text-primary disabled:opacity-20">
                          <ChevronRight size={12} />
                        </button>
                        <button onClick={() => removeStep(i)}
                          className="opacity-0 group-hover:opacity-100 text-text-dim hover:text-status-error">
                          <X size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* 添加步骤 */}
              {addStepOpen ? (
                <div className="bg-ide-bg border border-ide-border rounded p-3 mb-3 space-y-3">
                  <div className="flex gap-3">
                    <div className="flex-1">
                      <label className="text-2xs text-text-dim block mb-1">服务器</label>
                      <select value={stepServer} onChange={e => { setStepServer(e.target.value); setStepTool('') }}
                        className="w-full bg-ide-panel border border-ide-border rounded px-2 py-1.5 text-xs text-text-primary outline-none">
                        <option value="">选择服务器...</option>
                        {servers.filter(s => s.tool_count > 0).map(s => (
                          <option key={s.name} value={s.name}>{cn(s.name, SERVER_CN) || s.name} ({s.tool_count})</option>
                        ))}
                      </select>
                    </div>
                    <div className="flex-1">
                      <label className="text-2xs text-text-dim block mb-1">工具</label>
                      <select value={stepTool} onChange={e => setStepTool(e.target.value)}
                        disabled={!stepServer}
                        className="w-full bg-ide-panel border border-ide-border rounded px-2 py-1.5 text-xs text-text-primary outline-none disabled:opacity-40">
                        <option value="">选择工具...</option>
                        {serverTools.map(t => (
                          <option key={t.name} value={t.name}>{cn(t.name, TOOL_CN)} — {t.name}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="text-2xs text-text-dim block mb-1">参数 (JSON)</label>
                    <textarea value={stepParams} onChange={e => setStepParams(e.target.value)}
                      rows={2} spellCheck={false}
                      className="w-full bg-ide-panel border border-ide-border rounded px-2 py-1.5 text-xs text-text-primary font-mono outline-none focus:border-accent/50 resize-none" />
                  </div>
                  <div className="flex gap-2">
                    <button onClick={addStep} disabled={!stepServer || !stepTool}
                      className="px-3 py-1.5 text-xs bg-accent text-white rounded hover:bg-accent-hover disabled:opacity-40">添加</button>
                    <button onClick={() => setAddStepOpen(false)}
                      className="px-3 py-1.5 text-xs text-text-secondary border border-ide-border rounded hover:text-text-primary">取消</button>
                  </div>
                </div>
              ) : (
                <button onClick={() => setAddStepOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-accent border border-dashed border-accent/30 rounded hover:bg-accent/5 transition-colors">
                  <Plus size={13} /> 添加步骤
                </button>
              )}

              {/* 编辑器操作 */}
              <div className="flex gap-2 mt-4 pt-3 border-t border-ide-border">
                <button onClick={saveWorkflow} disabled={!editorName.trim() || editorSteps.length === 0}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-white bg-accent rounded hover:bg-accent-hover disabled:opacity-40">
                  <Save size={13} /> 保存
                </button>
                <button onClick={executeAdhoc} disabled={editorSteps.length === 0 || running}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-accent border border-accent/30 rounded hover:bg-accent/10 disabled:opacity-40">
                  <Play size={13} /> 执行测试
                </button>
                <button onClick={cancelEdit}
                  className="px-3 py-1.5 text-xs text-text-secondary border border-ide-border rounded hover:text-text-primary">取消</button>
              </div>
            </div>
          )}

          {/* ======== 主体：工作流 + 工具 ======== */}
          <div className="grid grid-cols-2 gap-4 mb-5">
            {/* 工作流列表 */}
            <div className="bg-ide-sidebar border border-ide-border rounded overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-2.5 border-b border-ide-border">
                <GitBranch size={14} className="text-text-dim" />
                <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">工作流</span>
                <span className="ml-auto text-2xs text-text-dim">{workflows.length}</span>
              </div>
              <div className="divide-y divide-ide-border max-h-[360px] overflow-y-auto">
                {workflows.length === 0 ? (
                  <div className="px-4 py-6 text-center text-text-dim text-xs">暂无可用工作流</div>
                ) : (
                  <>
                    {/* 内置工作流 */}
                    {builtinWorkflows.map(name => (
                      <div key={name} className="flex items-center gap-2 px-4 py-2.5 hover:bg-ide-hover">
                        <div className="flex-1 min-w-0">
                          <span className="text-xs text-text-primary">{cn(name, WORKFLOW_CN)}</span>
                          <span className="text-2xs text-text-dim ml-2 font-mono">{name}</span>
                        </div>
                        <span className="text-2xs px-1.5 py-0.5 rounded bg-ide-bg text-text-dim border border-ide-border shrink-0">内置</span>
                        <button onClick={() => setRunDialog(name)} disabled={running}
                          className="shrink-0 flex items-center gap-1 px-2 py-1 text-2xs text-accent border border-accent/30 rounded hover:bg-accent/10 transition-colors disabled:opacity-40">
                          <Play size={10} /> 运行
                        </button>
                      </div>
                    ))}
                    {/* 动态工作流 */}
                    {dynamicWorkflows.map(name => (
                      <div key={name} className="flex items-center gap-2 px-4 py-2.5 hover:bg-ide-hover group">
                        <div className="flex-1 min-w-0">
                          <span className="text-xs text-text-primary">{cn(name, WORKFLOW_CN) || name}</span>
                          <span className="text-2xs text-text-dim ml-2 font-mono">{name}</span>
                        </div>
                        <span className="text-2xs px-1.5 py-0.5 rounded bg-accent/10 text-accent border border-accent/30 shrink-0">自定义</span>
                        <button onClick={() => setRunDialog(name)} disabled={running}
                          className="shrink-0 flex items-center gap-1 px-2 py-1 text-2xs text-accent border border-accent/30 rounded hover:bg-accent/10 transition-colors disabled:opacity-40">
                          <Play size={10} /> 运行
                        </button>
                        <button onClick={() => {
                          const dw = dynamicWfs.find(w => w.name === name)
                          apiGet(`/orchestrator/workflows/dynamic/${encodeURIComponent(name)}`)
                            .then(d => startEdit(d.name, d.steps, false))
                            .catch(e => setError(e.message))
                        }}
                          className="opacity-0 group-hover:opacity-100 text-text-dim hover:text-accent shrink-0">
                          <Edit3 size={13} />
                        </button>
                        <button onClick={() => deleteWorkflow(name)}
                          className="opacity-0 group-hover:opacity-100 text-text-dim hover:text-status-error shrink-0">
                          <Trash2 size={13} />
                        </button>
                      </div>
                    ))}
                  </>
                )}
              </div>
            </div>

            {/* 工具列表（带搜索） */}
            <div className="bg-ide-sidebar border border-ide-border rounded overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-2.5 border-b border-ide-border">
                <Wrench size={14} className="text-text-dim" />
                <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">工具</span>
                <span className="ml-auto text-2xs text-text-dim">{filteredTools.length}{filteredTools.length !== tools.length ? ` / ${tools.length}` : ''}</span>
              </div>
              {/* 搜索框 */}
              <div className="px-3 py-2 border-b border-ide-border">
                <div className="flex items-center gap-2 bg-ide-bg border border-ide-border rounded px-2">
                  <Search size={13} className="text-text-dim shrink-0" />
                  <input value={toolSearch} onChange={e => setToolSearch(e.target.value)}
                    placeholder="搜索工具名、分类..."
                    className="flex-1 bg-transparent py-1.5 text-xs text-text-primary outline-none placeholder:text-text-dim" />
                  {toolSearch && (
                    <button onClick={() => setToolSearch('')} className="text-text-dim hover:text-text-primary">
                      <X size={13} />
                    </button>
                  )}
                </div>
              </div>
              <div className="max-h-[300px] overflow-y-auto pb-1">
                {filteredTools.length === 0 ? (
                  <div className="px-4 py-6 text-center text-text-dim text-xs">
                    {toolSearch ? '无匹配工具' : '暂无注册工具'}
                  </div>
                ) : (
                  Object.entries(toolsByServer).map(([server, st]) => (
                    <ToolGroup key={server} server={server} tools={st} defaultOpen={!toolSearch} />
                  ))
                )}
              </div>
            </div>
          </div>

          {/* ======== 执行结果 ======== */}
          {lastResult && (
            <div className="bg-ide-sidebar border border-ide-border rounded overflow-hidden mb-4">
              <div className="flex items-center gap-2 px-4 py-2.5 border-b border-ide-border">
                {workflowSucceeded
                  ? <CheckCircle2 size={14} className="text-status-ok" />
                  : <XCircle size={14} className="text-status-error" />}
                <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">执行结果</span>
                <span className="text-2xs text-text-dim ml-2 font-mono">{lastResult.workflow}</span>
                <span className={`ml-auto text-2xs font-medium ${workflowSucceeded ? 'text-status-ok' : 'text-status-error'}`}>
                  {workflowSucceeded ? '成功' : '失败'}
                </span>
              </div>
              <div className="px-4 py-2 max-h-[240px] overflow-y-auto">
                {lastResult.error && (
                  <div className="flex items-center gap-2 py-1 text-xs text-status-error mb-1">
                    <AlertCircle size={13} className="shrink-0" />{lastResult.error}
                  </div>
                )}
                {(lastResult.steps || []).length === 0 && !lastResult.error ? (
                  <div className="py-3 text-center text-text-dim text-xs">无步骤信息</div>
                ) : (
                  (lastResult.steps || []).map((step, i) => (
                    <StepResultRow key={i} step={step} index={i} />
                  ))
                )}
              </div>
            </div>
          )}

          {/* 底部监控 */}
          {monitor && (
            <div className="flex items-center gap-4 text-2xs text-text-dim">
              <span className="flex items-center gap-1"><Clock size={11} />运行时间: {formatUptime(monitor.uptime_seconds)}</span>
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

      {/* 教程弹窗 */}
      {(showTutorial || localTutorial) && (
        <TutorialModal onClose={() => { onCloseTutorial(); setLocalTutorial(false) }} />
      )}
    </div>
  )
}
