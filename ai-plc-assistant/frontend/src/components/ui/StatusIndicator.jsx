import React from 'react'
import StatusDot from './StatusDot'

/**
 * StatusIndicator — 状态指示器（含标签 + 值）
 *
 * 用于顶部状态栏，显示"标签：值"对，带状态圆点。
 *
 * 用法：
 *   <StatusIndicator label="PLC" value="S7-1200" status="connected" />
 *   <StatusIndicator label="后端" value="离线" status="error" />
 */
export default function StatusIndicator({
  label,
  value,
  status = 'neutral',
  icon: Icon,
  onClick,
  className = '',
  title,
}) {
  const clickable = !!onClick
  return (
    <div
      onClick={onClick}
      title={title || `${label}: ${value}`}
      className={`flex items-center gap-1.5 px-2 h-full text-2xs ${
        clickable ? 'cursor-pointer hover:bg-ide-hover rounded' : ''
      } ${className}`}
      role={clickable ? 'button' : 'status'}
      tabIndex={clickable ? 0 : undefined}
    >
      <StatusDot status={status} size={6} />
      {Icon && <Icon size={11} className="text-text-dim" />}
      <span className="text-text-dim">{label}</span>
      <span className="text-text-secondary tabular-nums">{value}</span>
    </div>
  )
}
