import { useState, useRef, useEffect } from 'react'
import { Circle, ChevronDown } from 'lucide-react'
import StatusIndicator from '../components/ui/StatusIndicator'

/**
 * GlobalStatusBar — 全局状态栏
 *
 * 按主计划 §7.3 优先级排列（左侧权重高）：
 * 安全模式 > PLC > TIA > PLCSIM > 后端 > 当前项目 > 当前 AI 模型
 *
 * 状态必须包含文字，不得只显示彩色圆点（使用 StatusIndicator）。
 *
 * Batch 4：PLC/TIA/PLCSIM/后端/安全模式 打桩显示"未连接/未启用"，
 * 后续 Batch 接入真实数据源。
 */

export default function GlobalStatusBar({
  currentProject,
  models,
  selectedModel,
  onSelectModel,
}) {
  const [showModelMenu, setShowModelMenu] = useState(false)
  const modelRef = useRef(null)

  const currentModel = models.find((m) => m.id === selectedModel)

  useEffect(() => {
    const handler = (e) => {
      if (modelRef.current && !modelRef.current.contains(e.target)) setShowModelMenu(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div className="flex-1 flex items-center justify-end gap-1 overflow-x-auto">
      {/* 安全模式 — 优先级最高 */}
      <StatusIndicator
        label="安全模式"
        value="只读"
        status="readonly"
        title="当前安全等级：Level 0 只读"
      />

      {/* PLC 状态 */}
      <StatusIndicator
        label="PLC"
        value="未连接"
        status="offline"
        title="PLC 未连接"
      />

      {/* TIA Portal 状态 */}
      <StatusIndicator
        label="TIA"
        value="未启动"
        status="offline"
        title="TIA Portal Openness 未启动"
      />

      {/* PLCSIM 状态 */}
      <StatusIndicator
        label="PLCSIM"
        value="未启用"
        status="neutral"
        title="PLCSIM 仿真未启用"
      />

      {/* 后端状态 */}
      <StatusIndicator
        label="后端"
        value="未连接"
        status="offline"
        title="后端 API 不可达"
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
