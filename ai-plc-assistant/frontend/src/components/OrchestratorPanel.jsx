import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  RefreshCw, Play, Server, Wrench, GitBranch,
  CheckCircle2, XCircle, Loader2, AlertCircle,
  ChevronDown, ChevronRight, Activity, Clock,
  Search, Plus, Trash2, Save, GripVertical, X,
  Edit3, HelpCircle,
} from 'lucide-react'
import { API_BASE } from '../api'

// ================================================================
// 中文映射
// ================================================================

const WORKFLOW_CN = {
  s7_monitor: 'S7 监控',
  tia_full_pipeline: 'TIA 全流水线',
  robot_pick_place: '机器人取放',
  robot_monitor: '机器人监控',
  s7_safety_loop: 'S7 安全闭环',
}

const CATEGORY_CN = {
  s7: 'S7 通信',
  tia: 'TIA 工程',
  safety: '安全',
  monitoring: '监控',
  control: '控制',
  engineering: '工程',
  desktop: '桌面',
  pipeline: '流水线',
  uncategorized: '未分类',
}

const SERVER_CN = {
  'plc-mcp-bridge': 'PLC 桥接',
  'tia-mcp': 'TIA Portal',
  'opcua-mcp': 'OPC UA',
  'modbus-mcp': 'Modbus',
  'mitsubishi-mcp': '三菱',
  'robot-mcp': '机器人',
  'desktop-mcp': '桌面',
  'test-echo': '测试',
}

const TOOL_CN = {
  // plc-mcp-bridge (65 工具)
  plc_add_tag: '添加标签', plc_apply: '应用配置', plc_archive_project: '归档项目',
  plc_archive_to_golden: '归档到模板', plc_check_consistency: '一致性检查',
  plc_check_tag_conflicts: '标签冲突检查', plc_close_project: '关闭项目',
  plc_compile_block: '编译块', plc_compile_project: '编译项目',
  plc_create_block: '创建块', plc_create_db: '创建DB', plc_create_instance: '创建实例',
  plc_create_project: '创建项目', plc_create_tag_table: '创建标签表',
  plc_create_udt: '创建UDT', plc_create_watch_table: '创建监视表',
  plc_delete_block: '删除块', plc_delete_db: '删除DB', plc_delete_tag: '删除标签',
  plc_delete_tag_table: '删除标签表', plc_delete_udt: '删除UDT',
  plc_delete_watch_table: '删除监视表', plc_download_project: '下载项目',
  plc_export_all_xml: '导出XML', plc_export_block: '导出块',
  plc_export_tags_csv: '导出CSV', plc_find_callers: '查找调用者',
  plc_find_free_address: '空闲地址', plc_find_unused_blocks: '未使用块',
  plc_fio_launch: '启动FIO', plc_fio_write_config: 'FIO配置',
  plc_get_block_details: '块详情', plc_get_block_interface: '块接口',
  plc_get_compiler_errors: '编译错误', plc_get_config: '获取配置',
  plc_get_device_config: '设备配置', plc_get_hardware_info: '硬件信息',
  plc_get_project_info: '项目信息', plc_get_rack_slot: '机架槽位',
  plc_get_state: '获取状态', plc_get_status_info: '状态信息',
  plc_get_tags: '获取标签', plc_go_offline: '下线', plc_go_online: '上线',
  plc_golden_restore: '模板恢复', plc_import_block: '导入块',
  plc_list_backups: '备份列表', plc_list_blocks: '列出块', plc_list_dbs: '列出DB',
  plc_list_devices: '设备列表', plc_list_instances: '实例列表',
  plc_list_tag_tables: '标签表', plc_list_udts: '列出UDT',
  plc_list_watch_tables: '监视表', plc_restore_from_golden: '从模板恢复',
  plc_run_pipeline: '运行流水线', plc_save_project: '保存项目',
  plc_search_tags: '搜索标签', plc_stop_instance: '停止实例',
  plc_switch_to_tcpip: '切换TCP/IP',
  s7_connect: 'S7连接', s7_disconnect: 'S7断开', s7_read: 'S7读取', s7_status: 'S7状态', s7_write: 'S7写入',
  // tia-mcp (15 工具)
  call_fb_in_ob1: '调用FB', compile_project: '编译项目', create_block: '创建块',
  create_ladder_block: '创建梯形图块', create_plc_tags: '创建PLC标签',
  download_to_plcsim: '下载到PLCSIM', export_block: '导出块',
  generate_and_import: '生成并导入', generate_scl_code: '生成SCL',
  go_offline: '下线', go_online: '上线', import_scl_file: '导入SCL',
  list_blocks: '列出块', list_devices: '设备列表', list_udts: '列出UDT',
  // robot-mcp (7 工具)
  control_conveyor: '传送带控制', get_status: '获取状态', go_home: '回原点',
  move_arm_to: '移动手臂', pick_item: '拾取', place_item: '放置', run_pick_cycle: '取放循环',
  // modbus-mcp (6 工具)
  read_coil: '读线圈', read_discrete_input: '读离散输入',
  read_register: '读寄存器', scan_devices: '扫描设备',
  write_coil: '写线圈', write_register: '写寄存器',
  // mitsubishi-mcp (3 工具)
  read_device: '读设备', read_devices: '批量读设备', write_device: '写设备',
}

function cn(s, map) { return map[s] || s }

// ================================================================
// API helpers
// ================================================================

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `HTTP ${res.status}`) }
  return res.json()
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `HTTP ${res.status}`) }
  return res.json()
}

async function apiDelete(path) {
  const res = await fetch(`${API_BASE}${path}`, { method: 'DELETE' })
  if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `HTTP ${res.status}`) }
  return res.json()
}

// ================================================================
// 子组件
// ================================================================

function StatCard({ icon: Icon, label, value, color }) {
  const dotColor = color === 'green' ? 'bg-status-ok' : color === 'red' ? 'bg-status-error' : 'bg-accent'
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

function StepResultRow({ step, index }) {
  const ok = step.ok !== false
  return (
    <div className="flex items-center gap-2 py-1 text-xs">
      <span className="text-text-dim w-5 text-right shrink-0">{index + 1}.</span>
      {ok ? <CheckCircle2 size={13} className="text-status-ok shrink-0" /> : <XCircle size={13} className="text-status-error shrink-0" />}
      <span className="text-text-primary font-mono truncate flex-1">{cn(step.tool, TOOL_CN)}</span>
      <span className="text-text-dim text-2xs font-mono">{step.tool}</span>
      {step.duration_ms != null && (
        <span className="text-text-dim text-2xs flex items-center gap-1 shrink-0">
          <Clock size={10} />{step.duration_ms}ms
        </span>
      )}
    </div>
  )
}

// ================================================================
// 主组件
// ================================================================

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

// ================================================================
// 工具分组
// ================================================================

function ToolGroup({ server, tools, defaultOpen }) {
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

// ================================================================
// 运行弹窗
// ================================================================

function RunDialog({ name, onRun, onCancel }) {
  const [input, setInput] = useState('{}')
  const [invalid, setInvalid] = useState(false)

  const handleChange = (v) => {
    setInput(v)
    try { JSON.parse(v); setInvalid(false) } catch { setInvalid(true) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90" onClick={onCancel}>
      <div className="bg-ide-sidebar border border-ide-border rounded shadow-lg w-[400px] p-4" onClick={e => e.stopPropagation()}>
        <h3 className="text-sm font-semibold text-text-bright mb-3">
          运行工作流: <span className="text-accent">{cn(name, WORKFLOW_CN) || name}</span>
        </h3>
        <label className="text-2xs text-text-dim mb-1 block">输入参数 (JSON)</label>
        <textarea value={input} onChange={e => handleChange(e.target.value)} rows={6} spellCheck={false}
          className={`w-full bg-ide-bg border rounded p-2 text-xs text-text-primary font-mono focus:outline-none resize-none ${
            invalid ? 'border-status-error/50' : 'border-ide-border focus:border-accent/50'
          }`} />
        {invalid && <div className="text-2xs text-status-error mt-1">JSON 格式无效</div>}
        <div className="flex justify-end gap-2 mt-3">
          <button onClick={onCancel}
            className="px-3 py-1.5 text-xs text-text-secondary hover:text-text-primary border border-ide-border rounded hover:bg-ide-hover transition-colors">取消</button>
          <button onClick={() => onRun(name, JSON.parse(input))} disabled={invalid}
            className="px-3 py-1.5 text-xs text-white bg-accent rounded hover:bg-accent-hover transition-colors flex items-center gap-1.5 disabled:opacity-40">
            <Play size={12} /> 运行
          </button>
        </div>
      </div>
    </div>
  )
}

function formatUptime(seconds) {
  if (seconds == null) return '--'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m`
  return `${Math.floor(seconds)}s`
}

// ================================================================
// 教程弹窗
// ================================================================

function TutorialModal({ onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90" onClick={onClose}>
      <div className="bg-ide-sidebar border border-ide-border rounded-lg shadow-2xl w-[680px] max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="sticky top-0 bg-ide-sidebar border-b border-ide-border px-5 py-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text-bright flex items-center gap-2">
            <HelpCircle size={18} className="text-accent" /> 编排管理教程
          </h2>
          <button onClick={onClose} className="text-text-dim hover:text-text-primary text-lg">✕</button>
        </div>

        <div className="px-5 py-4 space-y-6 text-xs">
          {/* 什么是编排层 */}
          <Section title="什么是编排层？" icon="🎯">
            <p>编排层（Orchestrator）是 AI PLC Assistant 的<strong>自动化中枢</strong>。它把多个工业协议服务器（S7、Modbus、TIA Portal、机器人等）串联起来，按预设的顺序自动执行操作。</p>
            <p className="mt-2">类比：就像工厂的流水线，每个工位做一件事，但整个流水线自动化运行。编排层就是这条流水线的控制中心。</p>
          </Section>

          {/* 工作流 */}
          <Section title="工作流是什么？" icon="🔀">
            <p><strong>工作流</strong> = 一组按顺序执行的工具调用。每个工作流解决一个完整的工业场景。</p>
            <div className="mt-2 bg-ide-bg border border-ide-border rounded p-3 space-y-1 font-mono text-text-secondary">
              <div className="text-accent">示例：robot_pick_place（机器人取放）</div>
              <div>1. get_status → 检查机器人状态</div>
              <div>2. go_home → 回原点</div>
              <div>3. control_conveyor → 启动传送带</div>
              <div>4. pick_item → 拾取工件</div>
              <div>5. control_conveyor → 传送带移动</div>
              <div>6. place_item → 放置工件</div>
              <div>7. go_home → 回原点</div>
            </div>
            <p className="mt-2 text-text-dim">内置工作流由 Python 代码定义，自定义工作流可通过可视化编辑器自由组合工具创建。</p>
          </Section>

          {/* 工具 */}
          <Section title="工具是什么？" icon="🔧">
            <p><strong>工具</strong> = 来自 MCP 服务器的单个操作能力。每个工具做一件具体的事。</p>
            <div className="mt-2 grid grid-cols-2 gap-2">
              <ToolCard server="PLC 桥接" count="65" desc="S7 读写、TIA 工程操作、PLCSIM" />
              <ToolCard server="TIA Portal" count="15" desc="编译、下载、导入SCL、创建块" />
              <ToolCard server="机器人" count="7" desc="取放、回原点、传送带控制" />
              <ToolCard server="Modbus" count="6" desc="线圈/寄存器读写、设备扫描" />
              <ToolCard server="三菱" count="3" desc="MC 协议读写" />
            </div>
          </Section>

          {/* 如何创建 */}
          <Section title="如何创建自定义工作流？" icon="✏️">
            <ol className="list-decimal list-inside space-y-2">
              <li>点击<strong>「新建工作流」</strong>按钮</li>
              <li>输入工作流名称（英文标识符，如 <code className="bg-ide-bg px-1 rounded text-accent">my_conveyor</code>）</li>
              <li>点击<strong>「添加步骤」</strong>，选择服务器和工具，填写参数</li>
              <li>重复添加步骤，组成完整的操作序列</li>
              <li>点击<strong>「保存」</strong>保存工作流，或点击<strong>「执行测试」</strong>立即运行</li>
            </ol>
            <p className="mt-2 text-text-dim">保存后，自定义工作流会出现在左侧工作流列表中，带「自定义」标签，可随时编辑或删除。</p>
          </Section>

          {/* 如何连接真实设备 */}
          <Section title="如何连接真实工业设备？" icon="🔌">
            <div className="space-y-3">
              <Step num={1} title="确保 MCP 服务器在运行">
                每个工业协议对应一个 MCP 服务器进程。启动后端时，编排层会自动连接 <code className="bg-ide-bg px-1 rounded text-accent">server_configs.py</code> 中配置的服务器。
              </Step>
              <Step num={2} title="S7 PLC 连接">
                通过 <code className="bg-ide-bg px-1 rounded text-accent">plc-mcp-bridge</code> 连接西门子 PLC。支持 TCP/IP 和 PLCSIM 仿真。使用 <code className="bg-ide-bg px-1 rounded text-accent">s7_connect</code> 工具建立连接。
              </Step>
              <Step num={3} title="TIA Portal 连接">
                需要安装 TIA Portal V21 + Openness API。通过 <code className="bg-ide-bg px-1 rounded text-accent">tia-mcp</code> 服务器操作 TIA 项目（创建、编译、下载）。
              </Step>
              <Step num={4} title="机器人连接">
                通过 <code className="bg-ide-bg px-1 rounded text-accent">robot-mcp</code> 连接。支持模拟模式（<code className="bg-ide-bg px-1 rounded text-accent">ROBOT_BACKEND=simulated</code>）和真实 Factory I/O 场景。
              </Step>
              <Step num={5} title="验证连接">
                在编排面板中查看「已连接服务器」数量。绿色表示已连接，红色表示未连接。工具列表中可看到所有可用工具。
              </Step>
            </div>
          </Section>

          {/* 安全 */}
          <Section title="安全机制" icon="🛡️">
            <p>编排层内置<strong>安全门（SafetyGate）</strong>机制：</p>
            <ul className="list-disc list-inside space-y-1 mt-2">
              <li>所有写入操作（write/apply/download/compile/create/delete）自动经过安全校验</li>
              <li>10 条互锁规则（温度、急停、压力、角度等）</li>
              <li>写入操作被拒绝时，工作流会中止并报错</li>
              <li>所有操作记录审计日志（HMAC 链式哈希）</li>
            </ul>
          </Section>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-ide-sidebar border-t border-ide-border px-5 py-3 flex justify-end">
          <button onClick={onClose}
            className="px-4 py-1.5 text-xs bg-accent text-white rounded hover:bg-accent-hover transition-colors">
            知道了
          </button>
        </div>
      </div>
    </div>
  )
}

function Section({ title, icon, children }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-text-primary mb-2">{icon} {title}</h3>
      <div className="text-text-secondary leading-relaxed">{children}</div>
    </div>
  )
}

function ToolCard({ server, count, desc }) {
  return (
    <div className="bg-ide-bg border border-ide-border rounded p-2">
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-text-primary font-medium">{server}</span>
        <span className="text-2xs text-accent">{count} 工具</span>
      </div>
      <div className="text-2xs text-text-dim">{desc}</div>
    </div>
  )
}

function Step({ num, title, children }) {
  return (
    <div className="flex gap-2">
      <span className="w-5 h-5 rounded-full bg-accent/20 text-accent text-2xs flex items-center justify-center shrink-0 mt-0.5">{num}</span>
      <div>
        <div className="font-medium text-text-primary mb-0.5">{title}</div>
        <div className="text-text-dim leading-relaxed">{children}</div>
      </div>
    </div>
  )
}