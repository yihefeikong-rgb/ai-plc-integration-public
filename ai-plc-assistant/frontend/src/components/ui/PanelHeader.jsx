import React from 'react'

/**
 * PanelHeader — 面板标题栏
 *
 * 用法：
 *   <PanelHeader icon={Server} title="系统状态">右侧自定义内容</PanelHeader>
 */
export default function PanelHeader({ icon: Icon, title, children, className = '', actions }) {
  return (
    <div className={`panel-header ${className}`}>
      {Icon && <Icon size={14} className="text-accent" />}
      {title && <span className="flex-1">{title}</span>}
      {children}
      {actions && <div className="ml-auto flex items-center gap-1">{actions}</div>}
    </div>
  )
}
