import React from 'react'
import StatusDot from './StatusDot'

/**
 * StatusBadge — 状态徽章（圆点 + 文字）
 *
 * 工业工作台要求"状态必须包含文字，不得只显示彩色圆点"。
 *
 * 用法：
 *   <StatusBadge status="connected" label="PLC 已连接" />
 *   <StatusBadge status="error" label="后端离线" />
 */

const STATUS_TO_BADGE_CLASS = {
  ok: 'status-badge-ok',
  connected: 'status-badge-ok',
  running: 'status-badge-ok',
  warn: 'status-badge-warn',
  warning: 'status-badge-warn',
  connecting: 'status-badge-warn',
  paused: 'status-badge-warn',
  error: 'status-badge-error',
  danger: 'status-badge-error',
  offline: 'status-badge-error',
  info: 'status-badge-info',
  neutral: 'status-badge-neutral',
  unknown: 'status-badge-neutral',
  readonly: 'status-badge-neutral',
  disabled: 'status-badge-neutral',
  ai: 'status-badge-ai',
}

export default function StatusBadge({ status = 'neutral', label, icon: Icon, className = '' }) {
  const cls = STATUS_TO_BADGE_CLASS[status] || 'status-badge-neutral'
  return (
    <span
      className={`status-badge ${cls} ${className}`}
      role="status"
      aria-label={label}
    >
      <StatusDot status={status} size={6} />
      {Icon && <Icon size={10} />}
      {label && <span>{label}</span>}
    </span>
  )
}
