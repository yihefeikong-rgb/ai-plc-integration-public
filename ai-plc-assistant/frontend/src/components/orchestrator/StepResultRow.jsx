// 执行结果步骤行
import { CheckCircle2, XCircle, Clock } from 'lucide-react'
import { cn, TOOL_CN } from './constants'

export default function StepResultRow({ step, index }) {
  const ok = step.ok === true
  return (
    <div className="flex items-center gap-2 py-1 text-xs">
      <span className="text-text-dim w-5 text-right shrink-0">{index + 1}.</span>
      {ok ? <CheckCircle2 size={13} className="text-status-ok shrink-0" /> : <XCircle size={13} className="text-status-error shrink-0" />}
      <span className="text-text-primary font-mono truncate flex-1">{cn(step.tool, TOOL_CN)}</span>
      <span className="text-text-dim text-2xs font-mono">{step.tool}</span>
      {step.duration_ms != null && (
        <span className="text-text-dim text-2xs flex items-center gap-1 shrink-0">
          <Clock size={10} />{step.duration_ms}ms
        </span>
      )}
    </div>
  )
}
