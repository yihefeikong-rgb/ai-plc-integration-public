import React from 'react'

/**
 * StatusDot — 状态圆点
 *
 * 用法：
 *   <StatusDot status="ok" />
 *   <StatusDot status="connecting" />
 *
 * 支持状态：neutral / unknown / offline / connecting / connected / running /
 *           paused / warning / error / danger / readonly / disabled / ai / ok / info
 */

const STATUS_TO_CLASS = {
  neutral: 'status-dot-neutral',
  unknown: 'status-dot-neutral',
  offline: 'status-dot-neutral',
  connecting: 'status-dot-connecting',
  connected: 'status-dot-ok',
  running: 'status-dot-running',
  paused: 'status-dot-info',
  warning: 'status-dot-warn',
  warn: 'status-dot-warn',
  error: 'status-dot-error',
  danger: 'status-dot-error',
  readonly: 'status-dot-neutral',
  disabled: 'status-dot-neutral',
  ai: 'status-dot-ai',
  ok: 'status-dot-ok',
  info: 'status-dot-info',
}

export default function StatusDot({ status = 'neutral', size = 8, className = '' }) {
  const cls = STATUS_TO_CLASS[status] || 'status-dot-neutral'
  return (
    <span
      className={`status-dot ${cls} ${className}`}
      style={{ width: size, height: size }}
      aria-hidden="true"
    />
  )
}
