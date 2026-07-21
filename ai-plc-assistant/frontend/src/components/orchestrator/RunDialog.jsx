// 运行工作流弹窗
import { useState } from 'react'
import { Play } from 'lucide-react'
import { cn, WORKFLOW_CN } from './constants'

export function formatUptime(seconds) {
  if (seconds == null) return '--'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m`
  return `${Math.floor(seconds)}s`
}

export default function RunDialog({ name, onRun, onCancel }) {
  const [input, setInput] = useState('{}')
  const [invalid, setInvalid] = useState(false)

  const handleChange = (v) => {
    setInput(v)
    try { JSON.parse(v); setInvalid(false) } catch { setInvalid(true) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90" onClick={onCancel}>
      <div className="bg-ide-sidebar border border-ide-border rounded shadow-lg w-[400px] p-4" onClick={e => e.stopPropagation()}>
        <h3 className="text-sm font-semibold text-text-bright mb-3">
          运行工作流: <span className="text-accent">{cn(name, WORKFLOW_CN) || name}</span>
        </h3>
        <label className="text-2xs text-text-dim mb-1 block">输入参数 (JSON)</label>
        <textarea value={input} onChange={e => handleChange(e.target.value)} rows={6} spellCheck={false}
          className={`w-full bg-ide-bg border rounded p-2 text-xs text-text-primary font-mono focus:outline-none resize-none ${
            invalid ? 'border-status-error/50' : 'border-ide-border focus:border-accent/50'
          }`} />
        {invalid && <div className="text-2xs text-status-error mt-1">JSON 格式无效</div>}
        <div className="flex justify-end gap-2 mt-3">
          <button onClick={onCancel}
            className="px-3 py-1.5 text-xs text-text-secondary hover:text-text-primary border border-ide-border rounded hover:bg-ide-hover transition-colors">取消</button>
          <button onClick={() => onRun(name, JSON.parse(input))} disabled={invalid}
            className="px-3 py-1.5 text-xs text-white bg-accent rounded hover:bg-accent-hover transition-colors flex items-center gap-1.5 disabled:opacity-40">
            <Play size={12} /> 运行
          </button>
        </div>
      </div>
    </div>
  )
}
