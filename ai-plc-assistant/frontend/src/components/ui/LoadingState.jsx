import React from 'react'
import { Loader2 } from 'lucide-react'

/**
 * LoadingState — 加载状态
 *
 * 用法：
 *   <LoadingState label="加载中..." />
 *   <LoadingState label="AI 解析中" icon={Bot} />
 */
export default function LoadingState({
  label = '加载中...',
  icon: Icon,
  className = '',
}) {
  return (
    <div className={`state-container loading ${className}`}>
      {Icon ? (
        <Icon size={28} className="state-icon animate-pulse" />
      ) : (
        <Loader2 size={24} className="state-icon animate-spin" />
      )}
      <div className="text-sm text-text-secondary">{label}</div>
    </div>
  )
}
