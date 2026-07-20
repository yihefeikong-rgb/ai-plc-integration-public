import React from 'react'

/**
 * Button — 基础按钮组件
 *
 * Variants: default | primary | ghost | danger
 * Sizes: sm | md | lg
 *
 * 用法：
 *   <Button variant="primary" size="md" onClick={...}>保存</Button>
 *   <Button variant="danger" onClick={...}>删除</Button>
 */
const variantClass = {
  default: 'btn',
  primary: 'btn btn-primary',
  ghost: 'btn btn-ghost',
  danger: 'btn btn-danger',
}

const sizeClass = {
  sm: 'btn-sm',
  md: '',
  lg: 'btn-lg',
}

export default function Button({
  children,
  variant = 'default',
  size = 'md',
  disabled = false,
  loading = false,
  icon: Icon,
  onClick,
  type = 'button',
  className = '',
  title,
  ...rest
}) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      title={title}
      className={`${variantClass[variant] || variantClass.default} ${sizeClass[size] || ''} ${className}`}
      {...rest}
    >
      {loading ? (
        <span className="animate-spin" aria-hidden="true">⟳</span>
      ) : (
        Icon && <Icon size={size === 'sm' ? 11 : 13} />
      )}
      {children && <span>{children}</span>}
    </button>
  )
}
