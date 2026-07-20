import { useState, useRef, useEffect, useCallback } from 'react'
import { Circle, ChevronDown, Shield } from 'lucide-react'
import StatusIndicator from '../components/ui/StatusIndicator'
import { healthCheck, orchestratorHealth, listServers } from '../api'
import { SAFETY_LEVELS, DEFAULT_SAFETY_LEVEL } from '../platform/safetyLevels'

/**
 * GlobalStatusBar — 全局状态栏
 *
 * 按主计划 §7.3 优先级排列：安全模式 > PLC > TIA > PLCSIM > 后端 > 当前项目 > AI 模型
 *
 * D-4 填充：
 * - 后端：healthCheck() 真实状态
 * - MCP/编排：orchestratorHealth() 真实数量
 * - PLC/TIA/PLCSIM：listServers() 按服务器名字匹配推断
 * - 安全模式：接入 safetyLevels，支持点击切换等级（localStorage 持久化）
 */

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
  } catch {}
  return DEFAULT_SAFETY_LEVEL
}

// 按服务器名字匹配推断 PLC/TIA/PLCSIM 是否连接
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

export default function GlobalStatusBar({
  currentProject,
  models,
  selectedModel,
  onSelectModel,
}) {
  const [showModelMenu, setShowModelMenu] = useState(false)
  const [showSafetyMenu, setShowSafetyMenu] = useState(false)
  const [safetyLevel, setSafetyLevel] = useState(loadSafetyLevel)
  const [backendHealth, setBackendHealth] = useState(null)
  const [orchHealth, setOrchHealth] = useState(null)
  const [serverMatches, setServerMatches] = useState({ plc: false, tia: false, plcsim: false })
  const modelRef = useRef(null)
  const safetyRef = useRef(null)

  const currentModel = models.find((m) => m.id === selectedModel)

  // D-4：轮询后端/编排/服务器状态（每 15s）
  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      try {
        const h = await healthCheck()
        if (!cancelled) setBackendHealth(h)
      } catch {
        if (!cancelled) setBackendHealth(null)
      }
      try {
        const o = await orchestratorHealth()
        if (!cancelled) setOrchHealth(o)
      } catch {
        if (!cancelled) setOrchHealth(null)
      }
      try {
        const s = await listServers()
        if (!cancelled) setServerMatches(matchServers(s?.servers || s))
      } catch {
        // 编排层不可达，保持未连接
      }
    }
    poll()
    const timer = setInterval(poll, 15000)
    return () => { cancelled = true; clearInterval(timer) }
  }, [])

  // 外部点击关闭模型菜单 + 安全菜单
  useEffect(() => {
    const handler = (e) => {
      if (modelRef.current && !modelRef.current.contains(e.target)) setShowModelMenu(false)
      if (safetyRef.current && !safetyRef.current.contains(e.target)) setShowSafetyMenu(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleSelectSafety = useCallback((level) => {
    setSafetyLevel(level)
    try { localStorage.setItem(SAFETY_STORAGE_KEY, level.id) } catch {}
    setShowSafetyMenu(false)
  }, [])

  const backendOk = backendHealth != null
  const mcpConnected = orchHealth?.servers_connected > 0

  return (
    <div className="flex-1 flex items-center justify-end gap-1 overflow-x-auto">
      {/* 安全模式 — 优先级最高，可点击切换等级 */}
      <div ref={safetyRef} className="relative flex items-center">
        <StatusIndicator
          label="安全模式"
          value={safetyLevel.label}
          status={safetyLevel.tone}
          icon={Shield}
          onClick={() => setShowSafetyMenu(!showSafetyMenu)}
          title={`当前安全等级：Level ${safetyLevel.level} ${safetyLevel.label} — ${safetyLevel.description}（点击切换）`}
        />
        {showSafetyMenu && (
          <div className="absolute right-0 top-full mt-0.5 bg-ide-sidebar border border-ide-border rounded shadow-xl z-dropdown min-w-[220px] py-1">
            <div className="px-3 py-1 text-2xs text-text-dim uppercase tracking-wider border-b border-ide-border">
              安全等级
            </div>
            {SAFETY_LEVELS_LIST.map((level) => (
              <button
                key={level.id}
                type="button"
                onClick={() => handleSelectSafety(level)}
                className={`w-full text-left px-3 py-1.5 text-xs flex items-start gap-2 ${
                  level.id === safetyLevel.id
                    ? 'bg-accent/15 text-accent'
                    : 'text-text-secondary hover:bg-ide-hover'
                }`}
              >
                <Circle
                  size={7}
                  fill={level.id === safetyLevel.id ? '#4EC9B0' : '#6A6A6A'}
                  className={level.id === safetyLevel.id ? 'text-status-ok mt-1' : 'text-text-dim mt-1'}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-2xs">L{level.level}</span>
                    <span>{level.label}</span>
                  </div>
                  <div className="text-2xs text-text-dim mt-0.5">{level.description}</div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* PLC 状态 */}
      <StatusIndicator
        label="PLC"
        value={serverMatches.plc ? '已连接' : '未连接'}
        status={serverMatches.plc ? 'connected' : 'offline'}
        title={serverMatches.plc ? 'PLC MCP 服务器已连接' : 'PLC 未连接（需 plc-mcp-bridge 服务器运行）'}
      />

      {/* TIA Portal 状态 */}
      <StatusIndicator
        label="TIA"
        value={serverMatches.tia ? '已启动' : '未启动'}
        status={serverMatches.tia ? 'connected' : 'offline'}
        title={serverMatches.tia ? 'TIA MCP 服务器已连接' : 'TIA Portal Openness 未启动'}
      />

      {/* PLCSIM 状态 */}
      <StatusIndicator
        label="PLCSIM"
        value={serverMatches.plcsim ? '已启用' : '未启用'}
        status={serverMatches.plcsim ? 'connected' : 'neutral'}
        title={serverMatches.plcsim ? 'PLCSIM 仿真已启用' : 'PLCSIM 仿真未启用'}
      />

      {/* 后端状态 */}
      <StatusIndicator
        label="后端"
        value={backendOk ? '已连接' : '未连接'}
        status={backendOk ? 'connected' : 'offline'}
        title={backendOk ? `后端 API 可达 (${backendHealth.version || 'v1'})` : '后端 API 不可达'}
      />

      {/* MCP 编排状态 */}
      <StatusIndicator
        label="MCP"
        value={mcpConnected ? `${orchHealth.servers_connected} 已连` : '未连接'}
        status={mcpConnected ? 'connected' : 'offline'}
        title={mcpConnected ? `编排层已连接 ${orchHealth.servers_connected} 个 MCP 服务器` : '编排层未连接 MCP 服务器'}
      />

      {/* 当前项目 */}
      <StatusIndicator
        label="项目"
        value={currentProject?.name || '未选择'}
        status={currentProject ? 'connected' : 'neutral'}
        title={currentProject ? `${currentProject.name} / ${currentProject.plc_type}` : '未选择项目'}
      />

      {/* AI 模型选择器 */}
      <div ref={modelRef} className="relative flex items-center">
        <button
          type="button"
          onClick={() => setShowModelMenu(!showModelMenu)}
          className="flex items-center gap-1.5 px-2 h-full text-2xs text-text-secondary hover:text-text-primary hover:bg-ide-hover rounded transition-colors"
          title="切换 AI 模型"
        >
          <Circle
            size={7}
            fill={currentModel?.enabled ? '#4EC9B0' : '#6A6A6A'}
            className={currentModel?.enabled ? 'text-status-ok' : 'text-text-dim'}
          />
          <span className="text-text-dim">AI</span>
          <span className="text-text-secondary">{currentModel?.name || selectedModel}</span>
          <ChevronDown size={10} className="text-text-dim" />
        </button>

        {showModelMenu && (
          <div className="absolute right-0 top-full mt-0.5 bg-ide-sidebar border border-ide-border rounded shadow-xl z-dropdown min-w-[180px] py-1">
            {models.map((m) => (
              <button
                key={m.id}
                type="button"
                disabled={!m.enabled}
                onClick={() => { onSelectModel(m.id); setShowModelMenu(false) }}
                className={`w-full text-left px-4 py-1.5 text-xs flex items-center gap-2 ${
                  m.id === selectedModel
                    ? 'bg-accent/15 text-accent'
                    : m.enabled
                    ? 'text-text-secondary hover:bg-ide-hover'
                    : 'text-text-dim cursor-not-allowed'
                }`}
              >
                <Circle
                  size={6}
                  fill={m.enabled ? '#4EC9B0' : '#6A6A6A'}
                  className={m.enabled ? 'text-status-ok' : 'text-text-dim'}
                />
                {m.name}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
