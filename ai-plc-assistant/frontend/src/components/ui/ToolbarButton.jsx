import React from 'react'

/**
 * ToolbarButton — 工具栏按钮（顶部菜单/工具栏专用）
 *
 * 比 Button 更紧凑，适配 48px 顶部工具栏。
 *
 * 用法：
 *   <ToolbarButton onClick={...}>项目</ToolbarButton>
 *   <ToolbarButton active={true}>视图</ToolbarButton>
 */
export default function ToolbarButton({
  children,
  onClick,
  active = false,
  disabled = false,
  className = '',
  title,
  ...rest
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`px-3 py-1 text-xs rounded transition-colors ${
        active
          ? 'bg-ide-active text-text-primary'
          : 'text-text-secondary hover:text-text-primary hover:bg-ide-hover'
      } ${disabled ? 'cursor-not-allowed opacity-50' : ''} ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}
