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

// F-037/F-062 根治：合并 tabs + activeTab 为单一 state object，
// 消除"updater 内触发副作用"反模式（旧 closeTab 在 setTabs updater 内调 setActiveTab，
// React 18 StrictMode 双调用会触发两次 setActiveTab，React 19 严格模式可能告警）。
// 单 state 更新一次即完成 tabs 与 activeTab 的同步，无需跨 setter 协调。
export default function useTabs() {
  const [state, setState] = useState({
    tabs: [{ id: 'welcome', closable: false }],
    activeTab: 'welcome',
  })

  const setActiveTab = useCallback((id) => {
    setState((prev) => (prev.activeTab === id ? prev : { ...prev, activeTab: id }))
  }, [])

  const openTab = useCallback((id) => {
    setState((prev) => {
      if (prev.tabs.find((t) => t.id === id)) {
        // tab 已存在，只切换 activeTab
return prev.activeTab === id ? prev : { ...prev, activeTab: id }
      }
      // 新增 tab
      return { tabs: [...prev.tabs, { id, closable: true }], activeTab: id }
    })
  }, [])

  const closeTab = useCallback((id) => {
    setState((prev) => {
      const nextTabs = prev.tabs.filter((t) => t.id !== id)
      // 同一 setState 更新内决定 activeTab：若关闭的是当前激活 tab，切到最后一个
      const nextActive = prev.activeTab === id
        ? (nextTabs[nextTabs.length - 1]?.id || 'welcome')
        : prev.activeTab
      return { tabs: nextTabs, activeTab: nextActive }
    })
  }, [])

  return { tabs: state.tabs, activeTab: state.activeTab, setActiveTab, openTab, closeTab }
}
