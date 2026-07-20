import React from 'react'

/**
 * ErrorState — 错误状态
 *
 * 用法：
 *   <ErrorState title="加载失败" description={err.message} onRetry={handleRetry} />
 */
export default function ErrorState({
  icon: Icon,
  title = '出错了',
  description,
  onRetry,
  retryLabel = '重试',
  className = '',
}) {
  return (
    <div className={`state-container error ${className}`}>
      {Icon ? <Icon size={32} className="state-icon" /> : <span className="state-icon text-2xl">⚠</span>}
      <div className="text-sm">{title}</div>
      {description && (
        <div className="text-xs text-text-dim break-all">{description}</div>
      )}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="btn btn-primary btn-sm mt-2"
        >
          {retryLabel}
        </button>
      )}
    </div>
  )
}
