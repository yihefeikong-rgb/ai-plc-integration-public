// Warning + Error 状态消息
import { AlertTriangle } from 'lucide-react'

export function WarningMessage({ content }) {
  return (
    <div className="flex items-start gap-2 p-3 bg-status-warn/10 border border-status-warn/30 rounded">
      <AlertTriangle size={14} className="text-status-warn shrink-0 mt-0.5" />
      <div className="flex-1 text-xs text-status-warn whitespace-pre-wrap">{content}</div>
    </div>
  )
}

export function ErrorMessage({ content }) {
  return (
    <div className="flex items-start gap-2 p-3 bg-status-error/10 border border-status-error/30 rounded">
      <AlertTriangle size={14} className="text-status-error shrink-0 mt-0.5" />
      <div className="flex-1 text-xs text-status-error whitespace-pre-wrap">{content}</div>
    </div>
  )
}
