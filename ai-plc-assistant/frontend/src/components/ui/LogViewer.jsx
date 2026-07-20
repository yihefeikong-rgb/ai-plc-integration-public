import React, { useEffect, useRef } from 'react'

/**
 * LogViewer — 日志查看器（自动滚动到底 + 等宽字体 + 级别色）
 *
 * 用法：
 *   <LogViewer logs={logs} levelField="level" messageField="message" timeField="time" />
 */
const levelStyles = {
  info: 'text-text-secondary',
  warn: 'text-status-warn',
  warning: 'text-status-warn',
  error: 'text-status-error',
  debug: 'text-text-dim',
  success: 'text-status-ok',
}

export default function LogViewer({
  logs = [],
  levelField = 'level',
  messageField = 'message',
  timeField = 'time',
  className = '',
  maxHeight = '100%',
  autoScroll = true,
  emptyText = '暂无日志',
}) {
  const endRef = useRef(null)

  useEffect(() => {
    if (autoScroll) endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs, autoScroll])

  if (!logs || logs.length === 0) {
    return (
      <div className={`text-center text-text-dim text-xs py-4 ${className}`}>
        {emptyText}
      </div>
    )
  }

  return (
    <div
      className={`overflow-y-auto font-mono text-2xs space-y-px ${className}`}
      style={{ maxHeight }}
      role="log"
    >
      {logs.map((log, i) => {
        const level = log[levelField] || 'info'
        const message = log[messageField] || ''
        const time = log[timeField] || ''
        return (
          <div key={i} className="flex gap-3 py-px">
            {time && <span className="text-text-dim shrink-0 w-16">{time}</span>}
            <span
              className={`shrink-0 w-10 uppercase ${
                levelStyles[level] || levelStyles.info
              }`}
            >
              {level}
            </span>
            <span className="text-text-secondary break-all">{message}</span>
          </div>
        )
      })}
      <div ref={endRef} />
    </div>
  )
}
