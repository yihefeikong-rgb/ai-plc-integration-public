// 任务进度 + 工具调用消息
import {
  Loader2, AlertTriangle, CheckCircle2, Circle, FileCode,
} from 'lucide-react'
import { StatusBadge } from '../../ui'
import { parseContent } from '../utils'
import { MSG_TYPES } from '../constants'
import PlaceholderMessage from './PlaceholderMessage'

// D-1：任务进度消息 — 进度条 + 步骤列表
export function TaskProgressMessage({ content }) {
  const data = parseContent(content)
  const steps = data.steps || []
  const progress = typeof data.progress === 'number' ? data.progress : 0
  const title = data.title || '任务进行中'
  if (!steps.length && !progress) return <PlaceholderMessage type={MSG_TYPES.TASK_PROGRESS} content={content} />
  return (
    <div className="space-y-2 p-3 bg-ide-panel/50 border border-ide-border rounded">
      <div className="flex items-center gap-2">
        <Loader2 size={14} className="text-accent animate-spin" />
        <span className="text-xs text-text-primary flex-1">{title}</span>
        <span className="text-2xs text-text-dim font-mono">{progress}%</span>
      </div>
      <div className="h-1 bg-ide-border rounded overflow-hidden">
        <div className="h-full bg-accent transition-all" style={{ width: `${progress}%` }} />
      </div>
      {steps.length > 0 && (
        <div className="space-y-1 mt-2">
          {steps.map((step, i) => {
            const status = step.status || 'pending'
            const Icon = status === 'done' ? CheckCircle2
              : status === 'running' ? Loader2
              : status === 'error' ? AlertTriangle
              : Circle
            const color = status === 'done' ? 'text-status-ok'
              : status === 'running' ? 'text-accent'
              : status === 'error' ? 'text-status-error'
              : 'text-text-dim'
            return (
              <div key={step.id || step.name || i} className="flex items-center gap-2 text-2xs">
                <Icon size={11} className={`${color} ${status === 'running' ? 'animate-spin' : ''} shrink-0`} />
                <span className={status === 'done' ? 'text-text-dim line-through' : 'text-text-secondary'}>
                  {step.label || step.name}
                </span>
                {step.detail && <span className="text-text-dim ml-auto truncate">{step.detail}</span>}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// D-1：工具调用消息 — 工具名 + 参数 + 结果
export function ToolCallMessage({ content }) {
  const data = parseContent(content)
  const tool = data.tool || data.name || 'unknown'
  const args = data.args || data.arguments || {}
  const result = data.result
  const status = data.status || 'done'
  const tone = status === 'error' ? 'danger' : status === 'running' ? 'info' : 'success'
  return (
    <div className="border border-ide-border rounded overflow-hidden">
      <div className="px-3 py-1.5 bg-ide-panel border-b border-ide-border flex items-center gap-2">
        <FileCode size={12} className="text-accent" />
        <span className="text-2xs font-mono text-accent flex-1">{tool}</span>
        <StatusBadge tone={tone}>{status}</StatusBadge>
      </div>
      {Object.keys(args).length > 0 && (
        <div className="px-3 py-2 border-b border-ide-border">
          <div className="text-2xs text-text-dim mb-1 uppercase tracking-wider">参数</div>
          <pre className="text-2xs text-text-secondary font-mono whitespace-pre-wrap overflow-x-auto">{JSON.stringify(args, null, 2)}</pre>
        </div>
      )}
      {result != null && (
        <div className="px-3 py-2">
          <div className="text-2xs text-text-dim mb-1 uppercase tracking-wider">结果</div>
          <pre className="text-2xs text-text-secondary font-mono whitespace-pre-wrap overflow-x-auto">
            {typeof result === 'string' ? result : JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
