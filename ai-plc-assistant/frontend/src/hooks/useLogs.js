import { useState, useCallback } from 'react'

// 日志容量上限，防止长会话（健康轮询/SSE 等持续打日志）导致数组无限增长
const MAX_LOGS = 50

export default function useLogs() {
  const [logs, setLogs] = useState([
    { time: new Date().toLocaleTimeString(), level: 'info', message: '系统已启动' },
  ])

  const addLog = useCallback((level, message) => {
    setLogs(prev => {
      const next = [...prev, { time: new Date().toLocaleTimeString(), level, message }]
      return next.length > MAX_LOGS ? next.slice(-MAX_LOGS) : next
    })
  }, [])

  return { logs, addLog }
}
