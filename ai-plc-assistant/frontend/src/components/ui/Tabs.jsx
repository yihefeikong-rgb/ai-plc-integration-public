import React, { useState, createContext, useContext } from 'react'

/**
 * Tabs — 标签页组件（Compound Component）
 *
 * 用法：
 *   <Tabs defaultValue="log">
 *     <Tabs.List>
 *       <Tabs.Trigger value="log">日志</Tabs.Trigger>
 *       <Tabs.Trigger value="ai">AI 调用</Tabs.Trigger>
 *     </Tabs.List>
 *     <Tabs.Content value="log">日志内容</Tabs.Content>
 *     <Tabs.Content value="ai">AI 调用内容</Tabs.Content>
 *   </Tabs>
 */

const TabsContext = createContext(null)

export default function Tabs({
  defaultValue,
  value: controlledValue,
  onValueChange,
  children,
  className = '',
}) {
  const [internalValue, setInternalValue] = useState(defaultValue)
  const value = controlledValue !== undefined ? controlledValue : internalValue
  const setValue = (v) => {
    if (controlledValue === undefined) setInternalValue(v)
    onValueChange?.(v)
  }
  return (
    <TabsContext.Provider value={{ value, setValue }}>
      {children}
    </TabsContext.Provider>
  )
}

function List({ children, className = '' }) {
  return <div className={`tabs-list ${className}`}>{children}</div>
}

function Trigger({ value, children, icon: Icon, disabled = false, closable = false, onClose }) {
  const ctx = useContext(TabsContext)
  if (!ctx) throw new Error('Tabs.Trigger must be used within <Tabs>')
  const active = ctx.value === value
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => ctx.setValue(value)}
      className={`tabs-trigger ${active ? 'active' : ''}`}
    >
      {Icon && <Icon size={12} />}
      <span>{children}</span>
      {closable && (
        <span
          role="button"
          tabIndex={0}
          onClick={(e) => { e.stopPropagation(); onClose?.(value) }}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); onClose?.(value) } }}
          className="ml-1 text-text-dim hover:text-text-primary"
          aria-label="关闭标签"
        >
          ✕
        </span>
      )}
    </button>
  )
}

function Content({ value, children, className = '', forceMount = false }) {
  const ctx = useContext(TabsContext)
  if (!ctx) throw new Error('Tabs.Content must be used within <Tabs>')
  const active = ctx.value === value
  if (!active && !forceMount) return null
  return (
    <div
      className={className}
      style={{ display: active ? 'block' : 'none' }}
      role="tabpanel"
      aria-hidden={!active}
    >
      {children}
    </div>
  )
}

Tabs.List = List
Tabs.Trigger = Trigger
Tabs.Content = Content
