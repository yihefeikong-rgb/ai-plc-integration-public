import { useState, useCallback, useRef, useEffect } from 'react'
import {
  Home, ArrowDownUp, Grip, Package, Play,
  AlertTriangle, Wifi, WifiOff, ChevronRight, ChevronLeft,
  ArrowUp, ArrowDown, Factory,
} from 'lucide-react'
import { API_BASE } from '../api'

// ---- 状态初始化 ----
const INITIAL_STATE = {
  connected: true,
  backend: 'simulated',
  emergencyStop: false,
  armPosition: 'home',
  grabClosed: false,
  itemDetected: false,
  conveyorEntry: false,
  conveyorExit: false,
  xRetracted: true,
  zUp: true,
}

const MAX_LOGS = 50
const LOCAL_API_TOKEN = import.meta.env.VITE_LOCAL_API_TOKEN

function timestamp() {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

export default function RobotPanel() {
  const [robot, setRobot] = useState(INITIAL_STATE)
  const [logs, setLogs] = useState([])
  const [executing, setExecuting] = useState(false)
  const logRef = useRef(null)

  // 自动滚动日志到底部
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [logs])

  const addLog = useCallback((action, result) => {
    setLogs(prev => {
      const next = [...prev, { time: timestamp(), action, result }]
      return next.length > MAX_LOGS ? next.slice(-MAX_LOGS) : next
    })
  }, [])

  const update = useCallback((patch) => {
    setRobot(prev => ({ ...prev, ...patch }))
  }, [])

  // ---- 急停 ----
  const toggleEmergencyStop = useCallback(() => {
    setRobot(prev => {
      const next = !prev.emergencyStop
      if (next) {
        addLog('模拟急停触发', '仅重置本地模拟状态；不控制真实设备')
        return { ...INITIAL_STATE, emergencyStop: true, connected: prev.connected, backend: prev.backend }
      }
      addLog('模拟急停解除', '本地模拟状态已恢复')
      return { ...prev, emergencyStop: false }
    })
  }, [addLog])

  // ---- 回位 ----
  const goHome = useCallback(() => {
    if (robot.emergencyStop || executing) return
    setExecuting(true)
    addLog('回位', '执行中...')
    setTimeout(() => {
      update({ armPosition: 'home', grabClosed: false, xRetracted: true, zUp: true })
      addLog('回位', '完成')
      setExecuting(false)
    }, 400)
  }, [robot.emergencyStop, executing, addLog, update])

  // ---- 拾取序列（5步，每步 500ms）----
  const pickItem = useCallback(() => {
    if (robot.emergencyStop || executing) return
    setExecuting(true)
    const steps = [
      { patch: { armPosition: 'extend', xRetracted: false }, log: '机械臂伸出' },
      { patch: { armPosition: 'lower', zUp: false }, log: 'Z轴下降' },
      { patch: { grabClosed: true }, log: '夹爪闭合' },
      { patch: { armPosition: 'raise', zUp: true }, log: 'Z轴上升' },
      { patch: { armPosition: 'retract', xRetracted: true }, log: '机械臂收回' },
    ]
    steps.forEach((step, i) => {
      setTimeout(() => {
        update(step.patch)
        addLog(`拾取 [${i + 1}/5]`, step.log)
        if (i === steps.length - 1) {
          update({ itemDetected: false })
          addLog('拾取', '完成')
          setExecuting(false)
        }
      }, (i + 1) * 500)
    })
  }, [robot.emergencyStop, executing, addLog, update])

  // ---- 放置序列（5步，反向）----
  const placeItem = useCallback(() => {
    if (robot.emergencyStop || executing) return
    setExecuting(true)
    const steps = [
      { patch: { armPosition: 'extend', xRetracted: false }, log: '机械臂伸出' },
      { patch: { armPosition: 'lower', zUp: false }, log: 'Z轴下降' },
      { patch: { grabClosed: false }, log: '夹爪张开' },
      { patch: { armPosition: 'raise', zUp: true }, log: 'Z轴上升' },
      { patch: { armPosition: 'home', xRetracted: true }, log: '机械臂回位' },
    ]
    steps.forEach((step, i) => {
      setTimeout(() => {
        update(step.patch)
        addLog(`放置 [${i + 1}/5]`, step.log)
        if (i === steps.length - 1) {
          addLog('放置', '完成')
          setExecuting(false)
        }
      }, (i + 1) * 500)
    })
  }, [robot.emergencyStop, executing, addLog, update])

  // ---- 自动循环（调用编排层工作流）----
  const runAutoCycle = useCallback(async () => {
    if (robot.emergencyStop || executing) return
    setExecuting(true)
    addLog('自动循环', '调用 robot_pick_place 工作流...')
    try {
      const res = await fetch(`${API_BASE}/orchestrator/workflows/robot_pick_place/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(LOCAL_API_TOKEN ? { 'X-Local-Api-Token': LOCAL_API_TOKEN } : {}),
        },
        body: JSON.stringify({ input: {} }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      if (data.ok) {
        addLog('自动循环', `工作流完成 (${data.total_duration_ms.toFixed(0)}ms)`)
        update({ armPosition: 'home', grabClosed: false, xRetracted: true, zUp: true })
      } else {
        addLog('自动循环', `工作流失败: ${data.error || '未知错误'}`)
      }
    } catch (e) {
      addLog('自动循环', `请求失败: ${e.message}`)
      // 降级：本地模拟
      update({ armPosition: 'home', grabClosed: false, xRetracted: true, zUp: true })
      addLog('自动循环', '降级为本地模拟')
    }
    setExecuting(false)
  }, [robot.emergencyStop, executing, addLog, update])

  // ---- 传送带控制 ----
  const conveyorAction = useCallback((action) => {
    if (robot.emergencyStop) return
    if (action === 'entry') {
      update({ conveyorEntry: true, conveyorExit: false })
      addLog('传送带', '入口启动')
    } else if (action === 'exit') {
      update({ conveyorEntry: false, conveyorExit: true })
      addLog('传送带', '出口启动')
    } else {
      update({ conveyorEntry: false, conveyorExit: false })
      addLog('传送带', '停止')
    }
  }, [robot.emergencyStop, addLog, update])

  // ---- 单轴控制 ----
  const armAxis = useCallback((direction) => {
    if (robot.emergencyStop || executing) return
    const map = {
      extend: { armPosition: 'extend', xRetracted: false },
      retract: { armPosition: 'retract', xRetracted: true },
      raise: { armPosition: 'raise', zUp: true },
      lower: { armPosition: 'lower', zUp: false },
    }
    update(map[direction])
    addLog('单轴控制', { extend: '伸出', retract: '收回', raise: '上升', lower: '下降' }[direction])
  }, [robot.emergencyStop, executing, addLog, update])

  const disabled = robot.emergencyStop || executing

  return (
    <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
      {/* ===== 标题栏 ===== */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Factory size={18} className="text-accent" />
          <h1 className="text-sm font-semibold text-text-bright">机器人模拟控制</h1>
        </div>
        <div className="flex items-center gap-2">
          {robot.connected
            ? <span className="flex items-center gap-1 text-2xs text-status-ok"><Wifi size={12} /> {robot.backend}</span>
            : <span className="flex items-center gap-1 text-2xs text-status-error"><WifiOff size={12} /> 未连接</span>
          }
        </div>
      </div>

      {/* ===== 机器人状态可视化 ===== */}
      <div className="bg-ide-sidebar border border-ide-border rounded p-4">
        <RobotVisualization robot={robot} />
      </div>

      {/* ===== 手动控制 ===== */}
      <div className="bg-ide-sidebar border border-ide-border rounded p-3 space-y-3">
        <div className="text-2xs font-semibold text-text-secondary uppercase tracking-wider">手动控制</div>

        {/* 主操作按钮 */}
        <div className="grid grid-cols-4 gap-2">
          <CtrlBtn icon={Home} label="回位" onClick={goHome} disabled={disabled} />
          <CtrlBtn icon={ArrowDownUp} label="拾取" onClick={pickItem} disabled={disabled} />
          <CtrlBtn icon={Package} label="放置" onClick={placeItem} disabled={disabled} />
          <CtrlBtn icon={Play} label="自动循环" onClick={runAutoCycle} disabled={disabled} accent />
        </div>

        {/* 传送带控制 */}
        <div>
          <div className="text-2xs text-text-dim mb-1.5">传送带</div>
          <div className="flex gap-2">
            <SmBtn label="入口 ▶" active={robot.conveyorEntry} onClick={() => conveyorAction('entry')} disabled={robot.emergencyStop} />
            <SmBtn label="出口 ▶" active={robot.conveyorExit} onClick={() => conveyorAction('exit')} disabled={robot.emergencyStop} />
            <SmBtn label="停止" onClick={() => conveyorAction('stop')} disabled={robot.emergencyStop} danger />
          </div>
        </div>

        {/* 机械臂单轴 */}
        <div>
          <div className="text-2xs text-text-dim mb-1.5">机械臂</div>
          <div className="flex gap-2">
            <SmBtn icon={ChevronRight} label="伸出" onClick={() => armAxis('extend')} disabled={disabled} />
            <SmBtn icon={ChevronLeft} label="收回" onClick={() => armAxis('retract')} disabled={disabled} />
            <SmBtn icon={ArrowUp} label="上升" onClick={() => armAxis('raise')} disabled={disabled} />
            <SmBtn icon={ArrowDown} label="下降" onClick={() => armAxis('lower')} disabled={disabled} />
          </div>
        </div>
      </div>

      {/* ===== 急停 + 状态信息 ===== */}
      <div className="flex gap-3">
        {/* 急停按钮 */}
        <button
          onClick={toggleEmergencyStop}
          className={`shrink-0 w-20 h-20 rounded-full border-4 font-bold text-xs flex flex-col items-center justify-center transition-all ${
            robot.emergencyStop
              ? 'border-status-error/50 bg-status-error/20 text-status-error animate-pulse'
              : 'border-status-error bg-status-error text-white hover:bg-status-error/80'
          }`}
        >
          <AlertTriangle size={18} className="mb-0.5" />
          急停
        </button>

        {/* 状态面板 */}
        <div className="flex-1 bg-ide-sidebar border border-ide-border rounded p-3">
          <div className="text-2xs font-semibold text-text-secondary uppercase tracking-wider mb-2">状态信息</div>
          <div className="grid grid-cols-3 gap-x-4 gap-y-1.5 text-xs">
            <StatusRow label="急停" value={robot.emergencyStop ? '触发' : '正常'} ok={!robot.emergencyStop} />
            <StatusRow label="连接" value={robot.connected ? robot.backend : '断开'} ok={robot.connected} />
            <StatusRow label="夹爪" value={robot.grabClosed ? '闭合' : '张开'} ok={!robot.grabClosed} />
            <StatusRow label="物料检测" value={robot.itemDetected ? '有物料' : '无'} ok={false} neutral />
            <StatusRow label="位置" value={robot.armPosition} ok />
            <StatusRow label="X轴" value={robot.xRetracted ? '收回' : '伸出'} ok={robot.xRetracted} />
            <StatusRow label="Z轴" value={robot.zUp ? '升起' : '下降'} ok={robot.zUp} />
            <StatusRow label="传送带入口" value={robot.conveyorEntry ? '运行' : '停止'} ok={robot.conveyorEntry} neutral />
            <StatusRow label="传送带出口" value={robot.conveyorExit ? '运行' : '停止'} ok={robot.conveyorExit} neutral />
          </div>
        </div>
      </div>

      {/* ===== 操作日志 ===== */}
      <div className="bg-ide-sidebar border border-ide-border rounded flex-1 min-h-[120px] flex flex-col">
        <div className="text-2xs font-semibold text-text-secondary uppercase tracking-wider px-3 pt-2 pb-1">操作日志</div>
        <div ref={logRef} className="flex-1 overflow-y-auto px-3 pb-2 font-mono text-2xs space-y-0.5">
          {logs.length === 0 && (
            <div className="text-text-dim py-4 text-center">暂无操作记录</div>
          )}
          {logs.map((l, i) => (
            <div key={i} className="flex gap-2">
              <span className="text-text-dim shrink-0">{l.time}</span>
              <span className="text-accent shrink-0">[{l.action}]</span>
              <span className={l.result === '完成' ? 'text-status-ok' : l.result.includes('失败') ? 'text-status-error' : 'text-text-secondary'}>
                {l.result}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ================================================================
// 子组件
// ================================================================

function RobotVisualization({ robot }) {
  const { armPosition, grabClosed, conveyorEntry, conveyorExit, xRetracted, zUp, itemDetected } = robot

  const endX = xRetracted ? 100 : (armPosition === 'extend' || armPosition === 'raise' || armPosition === 'lower') ? 145 : 75
  const endY = zUp ? 40 : (armPosition === 'lower') ? 85 : 40

  return (
    <div className="relative h-56 bg-ide-panel rounded overflow-hidden border border-ide-border">
      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 400 140" preserveAspectRatio="xMidYMid meet">
        {/* 背景 */}
        <rect x="0" y="0" width="400" height="140" fill="#1a1a2e" />

        {/* 地面 */}
        <rect x="0" y="100" width="400" height="40" fill="#252535" />

        {/* 传送带主体 */}
        <rect x="10" y="72" width="250" height="14" rx="2" fill="#3a3a4a" stroke="#4a4a5a" strokeWidth="0.5" />
        {/* 传送带表面 */}
        <g clipPath="url(#beltClip)">
          <rect x="10" y="72" width="250" height="14" fill="#444458" />
          {/* 滚动条纹 */}
          <g className={conveyorEntry ? 'animate-conveyor' : ''}>
            {Array.from({ length: 12 }, (_, i) => (
              <line key={i} x1={15 + i * 22} y1="74" x2={15 + i * 22} y2="84" stroke="#555568" strokeWidth="1.5" />
            ))}
          </g>
          {/* 物料 */}
          {itemDetected && (
            <rect x="120" y="67" width="22" height="16" rx="2" fill="#CCA700" opacity="0.9" className="transition-all duration-500">
              <animate attributeName="x" values="120;180;120" dur="4s" repeatCount="indefinite" />
            </rect>
          )}
        </g>
        <clipPath id="beltClip">
          <rect x="12" y="73" width="246" height="12" />
        </clipPath>
        {/* 传送带滚轮 */}
        <circle cx="22" cy="79" r="4" fill="#555" />
        <circle cx="248" cy="79" r="4" fill="#555" />

        {/* 入口传感器 */}
        <circle cx="50" cy="68" r="2.5" fill={conveyorEntry ? '#4EC9B0' : '#555'} className="transition-colors" />
        <text x="50" y="62" textAnchor="middle" fill="#666" fontSize="4">入口</text>

        {/* 取料区传感器 */}
        <circle cx="150" cy="68" r="2.5" fill={itemDetected ? '#CCA700' : '#555'} className="transition-colors" />
        <text x="150" y="62" textAnchor="middle" fill="#666" fontSize="4">检测</text>

        {/* 出口传感器 */}
        <circle cx="230" cy="68" r="2.5" fill={conveyorExit ? '#4EC9B0' : '#555'} className="transition-colors" />
        <text x="230" y="62" textAnchor="middle" fill="#666" fontSize="4">出口</text>

        {/* 放置区 */}
        <rect x="270" y="70" width="40" height="30" rx="3" fill="#252535" stroke="#3a3a4a" strokeWidth="0.5" strokeDasharray="2,2" />
        <text x="290" y="88" textAnchor="middle" fill="#444" fontSize="4">放置区</text>

        {/* 物料箱 */}
        <rect x="275" y="76" width="12" height="10" rx="1" fill="#3a3a4a" stroke="#4a4a5a" strokeWidth="0.3" />
        <rect x="292" y="76" width="12" height="10" rx="1" fill="#3a3a4a" stroke="#4a4a5a" strokeWidth="0.3" />

        {/* 出口传送带 */}
        <rect x="320" y="72" width="70" height="14" rx="2" fill="#3a3a4a" stroke="#4a4a5a" strokeWidth="0.5" />
        <g className={conveyorExit ? 'animate-conveyor' : ''}>
          {Array.from({ length: 4 }, (_, i) => (
            <line key={i} x1={325 + i * 22} y1="74" x2={325 + i * 22} y2="84" stroke="#555568" strokeWidth="1.5" />
          ))}
        </g>
        <circle cx="332" cy="79" r="4" fill="#555" />
        <circle cx="378" cy="79" r="4" fill="#555" />

        {/* 机械臂底座 */}
        <rect x="170" y="85" width="30" height="15" rx="2" fill="#4a4a5a" />
        <rect x="178" y="78" width="14" height="10" rx="2" fill="#007ACC" />

        {/* 机械臂大臂 */}
        <line x1="185" y1="78" x2={endX} y2={endY} stroke="#007ACC" strokeWidth="4" strokeLinecap="round"
          style={{ transition: 'all 0.4s ease' }} />

        {/* 关节 */}
        <circle cx="185" cy="78" r="4.5" fill="#007ACC" stroke="#1a1a2e" strokeWidth="0.5" />
        <circle cx={endX} cy={endY} r="3.5" fill="#4EC9B0" stroke="#1a1a2e" strokeWidth="0.5"
          style={{ transition: 'all 0.4s ease' }} />

        {/* 夹爪 */}
        <g style={{ transition: 'all 0.4s ease' }}>
          {grabClosed ? (
            <line x1={endX} y1={endY} x2={endX + 6} y2={endY + 10} stroke="#CCA700" strokeWidth="2.5" strokeLinecap="round" />
          ) : (
            <>
              <line x1={endX} y1={endY} x2={endX - 5} y2={endY + 12} stroke="#CCA700" strokeWidth="2" strokeLinecap="round" />
              <line x1={endX} y1={endY} x2={endX + 5} y2={endY + 12} stroke="#CCA700" strokeWidth="2" strokeLinecap="round" />
            </>
          )}
        </g>

        {/* 标签 */}
        <text x="185" y="112" textAnchor="middle" fill="#888" fontSize="5" fontFamily="monospace">位置: {armPosition}</text>
        <text x="185" y="120" textAnchor="middle" fill="#888" fontSize="5" fontFamily="monospace">夹爪: {grabClosed ? '闭合' : '张开'}</text>

        {/* 急停指示灯 */}
        <circle cx="385" cy="15" r="6" fill={robot.emergencyStop ? '#ef4444' : '#333'} className="transition-colors" />
        <text x="385" y="27" textAnchor="middle" fill={robot.emergencyStop ? '#ef4444' : '#555'} fontSize="5">急停</text>
      </svg>

      {/* CSS 动画 */}
      <style>{`
        @keyframes conveyorScroll {
          from { transform: translateX(0); }
          to { transform: translateX(22px); }
        }
        .animate-conveyor line {
          animation: conveyorScroll 0.5s linear infinite;
        }
      `}</style>
    </div>
  )
}

function CtrlBtn({ icon: Icon, label, onClick, disabled, accent }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex flex-col items-center gap-1 py-2.5 px-2 rounded border text-xs transition-colors ${
        disabled
          ? 'bg-ide-panel border-ide-border text-text-dim cursor-not-allowed'
          : accent
            ? 'bg-accent/10 border-accent/40 text-accent hover:bg-accent/20'
            : 'bg-ide-panel border-ide-border text-text-primary hover:border-accent/40 hover:text-accent'
      }`}
    >
      <Icon size={16} />
      <span>{label}</span>
    </button>
  )
}

function SmBtn({ icon: Icon, label, onClick, disabled, active, danger }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex items-center gap-1 px-2.5 py-1.5 rounded border text-2xs transition-colors ${
        disabled
          ? 'bg-ide-panel border-ide-border text-text-dim cursor-not-allowed'
          : danger
            ? 'border-status-error/40 text-status-error hover:bg-status-error/10'
            : active
              ? 'bg-accent/10 border-accent/40 text-accent'
              : 'bg-ide-panel border-ide-border text-text-secondary hover:border-accent/30 hover:text-text-primary'
      }`}
    >
      {Icon && <Icon size={12} />}
      {label}
    </button>
  )
}

function StatusRow({ label, value, ok, neutral }) {
  const color = neutral ? 'text-text-dim' : ok ? 'text-status-ok' : 'text-status-error'
  return (
    <div className="flex items-center justify-between">
      <span className="text-text-dim">{label}</span>
      <span className={color}>{value}</span>
    </div>
  )
}
