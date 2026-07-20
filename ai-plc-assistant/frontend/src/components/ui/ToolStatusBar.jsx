import { Loader2, CheckCircle2, AlertTriangle, XCircle, Info, Circle } from 'lucide-react'

/**
 * ToolStatusBar — PLC 工具页面统一状态栏（Batch 7）
 *
 * 按主计划 §10 统一 10 种状态：
 * idle / inputting / validation_failed / running / success / failed /
 * partial / no_result / offline / model_unavailable
 *
 * 用于 5 个 PLC 工具页面（梯形图/程序解析/IO表/变量分析/故障诊断）
 * 替代各页面自实现的 loading 显示，统一交互逻辑。
 */

const STATUS_CONFIG = {
  idle: { icon: Circle, label: '空闲', tone: 'neutral' },
  inputting: { icon: Info, label: '输入中', tone: 'neutral' },
  validation_failed: { icon: AlertTriangle, label: '校验失败', tone: 'warning' },
  running: { icon: Loader2, label: '执行中', tone: 'info', spin: true },
  success: { icon: CheckCircle2, label: '执行成功', tone: 'ok' },
  failed: { icon: XCircle, label: '执行失败', tone: 'error' },
  partial: { icon: CheckCircle2, label: '部分成功', tone: 'warning' },
  no_result: { icon: Info, label: '无结果', tone: 'neutral' },
  offline: { icon: XCircle, label: '后端离线', tone: 'offline' },
  model_unavailable: { icon: AlertTriangle, label: '模型不可用', tone: 'warning' },
}

const TONE_CLASS = {
  neutral: 'text-text-dim',
  info: 'text-accent',
  ok: 'text-status-ok',
  warning: 'text-status-warning',
  error: 'text-status-error',
  offline: 'text-status-offline',
}

export default function ToolStatusBar({ status = 'idle', message, model, className = '' }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.idle
  const Icon = cfg.icon
  const toneClass = TONE_CLASS[cfg.tone] || 'text-text-dim'
  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 border-b border-ide-border bg-ide-sidebar text-2xs ${className}`}>
      <Icon size={12} className={`${toneClass} ${cfg.spin ? 'animate-spin' : ''} shrink-0`} />
      <span className={`${toneClass} font-medium`}>{cfg.label}</span>
      {model && (
        <>
          <span className="text-text-dim">·</span>
          <span className="text-text-dim">
            模型: <span className="text-text-secondary font-mono">{model}</span>
          </span>
        </>
      )}
      {message && <span className="text-text-dim truncate flex-1 ml-2">{message}</span>}
    </div>
  )
}
