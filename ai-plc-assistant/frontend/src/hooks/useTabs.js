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
      return next
    })
    setActiveTab(prev => {
      if (prev !== id) return prev
      // 当前 tab 被关闭, 回到最后一个
      return tabs.filter(t => t.id !== id).pop()?.id || 'welcome'
    })
  }, [tabs])

  return { tabs, activeTab, setActiveTab, openTab, closeTab }
}
