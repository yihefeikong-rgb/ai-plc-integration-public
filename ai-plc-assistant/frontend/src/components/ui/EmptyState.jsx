import React from 'react'

/**
 * EmptyState — 空状态
 *
 * 用法：
 *   <EmptyState icon={FolderOpen} title="暂无项目" description="点击上方新建项目" />
 *   <EmptyState icon={Inbox} description="无搜索结果" />
 */
export default function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className = '',
}) {
  return (
    <div className={`state-container ${className}`}>
      {Icon && <Icon size={32} className="state-icon text-text-dim" />}
      {title && <div className="text-sm text-text-secondary">{title}</div>}
      {description && <div className="text-xs text-text-dim">{description}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
