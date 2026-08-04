import { useState, useRef, useEffect, useMemo } from 'react'
import { ChevronUp, ChevronDown } from 'lucide-react'
import LogViewer from '../components/ui/LogViewer'
import EmptyState from '../components/ui/EmptyState'

/**
 * BottomPanel — 底部面板（7 Tab，按日志前缀分类过滤）
 *
 * 按主计划 §7.6：日志 / AI 调用 / 任务 / PLC 通信 / TIA Openness / 问题 / 错误
 *
 * "日志"显示全部，其余 6 Tab 按 message 前缀或 level 过滤。
 * 折叠状态本地持久化（D-FE-012：挂载状态与折叠状态分离）。
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

// D-2：按 message 前缀或 level 过滤日志
const TAB_FILTERS = {
  log: () => true,
  ai: (log) => /\[(LLM|SSE|生成|对话|发送|附件)\]/.test(log.message),
  task: (log) => /\[(任务|后台|导入|导出|项目)\]/.test(log.message),
  plc: (log) => /\[(PLC|S7|Modbus|OPC\s?UA|MCP|snap7|plcsim)\]/i.test(log.message),
  tia: (log) => /\[(TIA|编译|下载|TiaWorker|tia-|工程态)\]/i.test(log.message),
  problem: (log) => log.level === 'warn',
  error: (log) => log.level === 'error',
}

const EMPTY_TEXT = {
  ai: '暂无 AI 调用记录（对话/生成/模型切换会在此显示）',
  task: '暂无任务记录（项目导入/导出/后台任务会在此显示）',
  plc: '暂无 PLC 通信记录（S7/Modbus/OPC UA 读写会在此显示）',
  tia: '暂无 TIA Openness 记录（编译/下载/导入会在此显示）',
  problem: '暂无警告记录',
  error: '暂无错误记录',
}

export default function BottomPanel({ logs, collapsed, setCollapsed, activeTab, setActiveTab }) {
  const endRef = useRef(null)

  // 各 Tab 计数与 activeTab 过滤结果：单次遍历日志数组一次完成，
  // 避免为每个 Tab 反复生成中间过滤数组、避免对整份日志重复过滤（O(n) 而非 O(7n)）
  const { filteredLogs, tabCounts } = useMemo(() => {
    const counts = { log: logs.length }
    TABS.forEach((tab) => {
      if (tab.id !== 'log') counts[tab.id] = 0
    })
    const filtered = []
    logs.forEach((log) => {
      TABS.forEach((tab) => {
        if (tab.id !== 'log' && TAB_FILTERS[tab.id](log)) {
          counts[tab.id] += 1
          if (tab.id === activeTab) filtered.push(log)
        }
      })
    })
    return { filteredLogs: activeTab === 'log' ? logs : filtered, tabCounts: counts }
  }, [logs, activeTab])

  useEffect(() => {
    if (!collapsed) {
      endRef.current?.scrollIntoView?.({ behavior: 'smooth' })
    }
  }, [filteredLogs, collapsed])

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
            className={`px-3 h-full text-2xs border-r border-ide-border transition-colors flex items-center gap-1 ${
              activeTab === tab.id && !collapsed
                ? 'text-text-primary bg-ide-bg border-b border-b-accent'
                : 'text-text-dim hover:text-text-secondary'
            }`}
          >
            {tab.label}
            <span className="text-text-dim">({tabCounts[tab.id] || 0})</span>
            {tab.id === 'error' && tabCounts[tab.id] > 0 && (
              <span className="w-1.5 h-1.5 rounded-full bg-status-error" />
            )}
            {tab.id === 'problem' && tabCounts[tab.id] > 0 && (
              <span className="w-1.5 h-1.5 rounded-full bg-status-warn" />
            )}
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
          {filteredLogs.length > 0 ? (
            <LogViewer logs={filteredLogs} autoScroll={false} className="h-32" />
          ) : (
            <EmptyState description={EMPTY_TEXT[activeTab] || '暂无数据'} />
          )}
          <div ref={endRef} />
        </div>
      )}
    </div>
  )
}
