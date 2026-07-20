import { useState, useRef, useEffect } from 'react'
import { ChevronUp, ChevronDown } from 'lucide-react'
import LogViewer from '../components/ui/LogViewer'
import EmptyState from '../components/ui/EmptyState'

/**
 * BottomPanel — 底部面板（扩展为 7 Tab）
 *
 * 按主计划 §7.6：日志 / AI 调用 / 任务 / PLC 通信 / TIA Openness / 问题 / 错误
 *
 * "日志"保留现有 LogViewer 行为。
 * 其余 6 Tab 显示明确空状态，不伪造数据。
 * 折叠状态本地持久化。
 */

const TABS = [
  { id: 'log', label: '日志' },
  { id: 'ai', label: 'AI 调用' },
  { id: 'task', label: '任务' },
  { id: 'plc', label: 'PLC 通信' },
  { id: 'tia', label: 'TIA Openness' },
  { id: 'problem', label: '问题' },
  { id: 'error', label: '错误' },
]

const EMPTY_TEXT = {
  ai: 'AI 调用记录 — 待接入（将显示模型/Token/延迟/回退信息）',
  task: '任务记录 — 待接入（将显示后台任务状态与进度）',
  plc: 'PLC 通信记录 — 待接入（将显示 S7/Modbus/OPC UA 读写日志）',
  tia: 'TIA Openness 记录 — 待接入（将显示编译/下载/导入日志）',
  problem: '问题记录 — 待接入（将显示警告与建议）',
  error: '错误记录 — 待接入（将显示错误详情与堆栈）',
}

export default function BottomPanel({ logs, collapsed, setCollapsed, activeTab, setActiveTab }) {
  const endRef = useRef(null)

  useEffect(() => {
    if (!collapsed) {
      endRef.current?.scrollIntoView?.({ behavior: 'smooth' })
    }
  }, [logs, collapsed])

  return (
    <div className="border-t border-ide-border bg-ide-panel">
      {/* Tab bar */}
      <div className="flex items-center h-8 border-b border-ide-border">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => {
              setActiveTab(tab.id)
              setCollapsed(false)
            }}
            className={`px-3 h-full text-2xs border-r border-ide-border transition-colors ${
              activeTab === tab.id && !collapsed
                ? 'text-text-primary bg-ide-bg border-b border-b-accent'
                : 'text-text-dim hover:text-text-secondary'
            }`}
          >
            {tab.label}
            {tab.id === 'log' && <span className="ml-1 text-text-dim">({logs.length})</span>}
          </button>
        ))}

        <div className="flex-1" />

        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="px-2 h-full text-text-dim hover:text-text-secondary"
          aria-label={collapsed ? '展开底部面板' : '折叠底部面板'}
        >
          {collapsed ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>

      {/* Panel content */}
      {!collapsed && (
        <div className="h-40 overflow-y-auto px-3 py-1">
          {activeTab === 'log' ? (
            <LogViewer logs={logs} autoScroll={false} className="h-32" />
          ) : (
            <EmptyState description={EMPTY_TEXT[activeTab] || '未接入数据'} />
          )}
          <div ref={endRef} />
        </div>
      )}
    </div>
  )
}
