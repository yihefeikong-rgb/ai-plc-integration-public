import { useState, useCallback } from 'react'

export default function useLogs() {
  const [logs, setLogs] = useState([
    { time: new Date().toLocaleTimeString(), level: 'info', message: '系统已启动' },
  ])

  const addLog = useCallback((level, message) => {
    setLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), level, message }])
  }, [])

  return { logs, addLog }
}
