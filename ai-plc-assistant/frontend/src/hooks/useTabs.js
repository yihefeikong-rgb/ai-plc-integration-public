import { useState, useCallback } from 'react'

export const TAB_LABELS = {
  welcome: '欢迎',
  chat: 'AI 助手',
  ladder: '梯形图生成',
  parse: '程序解析',
  diagnose: '故障诊断',
  'io-table': 'IO表生成',
  variables: '变量分析',
  settings: '设置',
  orchestrator: '编排管理',
  robot: '机器人',
}

export default function useTabs() {
  const [tabs, setTabs] = useState([{ id: 'welcome', closable: false }])
  const [activeTab, setActiveTab] = useState('welcome')

  const openTab = useCallback((id) => {
    setTabs(prev => {
      if (prev.find(t => t.id === id)) return prev
      return [...prev, { id, closable: true }]
    })
    setActiveTab(id)
  }, [])

  const closeTab = useCallback((id) => {
    setTabs(prev => {
      const next = prev.filter(t => t.id !== id)
      // 在 setTabs updater 内同步 setActiveTab，避免闭包 tabs 过期
      setActiveTab(cur => {
        if (cur !== id) return cur
        return next[next.length - 1]?.id || 'welcome'
      })
      return next
    })
  }, [])

  return { tabs, activeTab, setActiveTab, openTab, closeTab }
}
