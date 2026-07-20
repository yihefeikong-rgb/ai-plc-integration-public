import React from 'react'

/**
 * IconButton — 图标按钮
 *
 * 用法：
 *   <IconButton icon={Settings} label="设置" onClick={...} />
 *   <IconButton icon={X} label="关闭" variant="ghost" size="sm" />
 */
const sizeMap = {
  sm: { box: 'var(--control-h-sm)', icon: 12 },
  md: { box: 'var(--control-h-md)', icon: 14 },
  lg: { box: 'var(--control-h-lg)', icon: 16 },
}

export default function IconButton({
  icon: Icon,
  label,
  onClick,
  disabled = false,
  active = false,
  variant = 'ghost',
  size = 'md',
  title,
  className = '',
  ...rest
}) {
  const sz = sizeMap[size] || sizeMap.md
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      title={title || label}
      aria-label={label}
      className={`icon-btn ${active ? 'active' : ''} ${className}`}
      style={{ width: sz.box, height: sz.box }}
      {...rest}
    >
      {Icon && <Icon size={sz.icon} />}
    </button>
  )
}
