import { useState, useRef, useEffect } from 'react'
import { ChevronUp, ChevronDown, X } from 'lucide-react'

const tabs = [
  { id: 'log', label: '日志' },
  { id: 'output', label: '输出' },
  { id: 'ai', label: 'AI 调用' },
  { id: 'debug', label: '调试' },
]

const levelStyles = {
  info: 'text-text-secondary',
  warn: 'text-status-warn',
  error: 'text-status-error',
}

export default function LogPanel({ logs }) {
  const [collapsed, setCollapsed] = useState(true)
  const [activeTab, setActiveTab] = useState('log')
  const endRef = useRef(null)

  useEffect(() => {
    if (!collapsed) {
      endRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, collapsed])

  return (
    <div className="border-t border-ide-border bg-ide-panel">
      {/* Tab bar */}
      <div className="flex items-center h-8 border-b border-ide-border">
        {tabs.map((tab) => (
          <button
            key={tab.id}
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
          onClick={() => setCollapsed(!collapsed)}
          className="px-2 h-full text-text-dim hover:text-text-secondary"
        >
          {collapsed ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>

      {/* Panel content */}
      {!collapsed && (
        <div className="h-40 overflow-y-auto px-3 py-1 font-mono text-2xs">
          {activeTab === 'log' && (
            <div className="space-y-px">
              {logs.map((log, i) => (
                <div key={i} className="flex gap-3 py-px">
                  <span className="text-text-dim shrink-0 w-16">{log.time}</span>
                  <span className={`shrink-0 w-10 uppercase ${levelStyles[log.level] || 'text-text-secondary'}`}>
                    {log.level}
                  </span>
                  <span className="text-text-secondary break-all">{log.message}</span>
                </div>
              ))}
              <div ref={endRef} />
            </div>
          )}

          {activeTab === 'output' && (
            <div className="text-text-dim py-2">输出面板 — 程序生成结果将在此显示</div>
          )}

          {activeTab === 'ai' && (
            <div className="text-text-dim py-2">AI 调用记录 — API 请求和响应将在此显示</div>
          )}

          {activeTab === 'debug' && (
            <div className="text-text-dim py-2">调试信息 — 运行时调试数据将在此显示</div>
          )}
        </div>
      )}
    </div>
  )
}
