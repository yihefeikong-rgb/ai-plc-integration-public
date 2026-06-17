import { useState } from 'react'
import { FolderPlus } from 'lucide-react'

const PLC_TYPES = ['S7-1200', 'S7-1500', 'S7-300', 'S7-400', 'S7-200 SMART']
const TIA_VERSIONS = ['V18', 'V19', 'V17', 'V16']
const LANGUAGES = ['SCL', 'LAD', 'FBD', 'STL']

export default function CreateProjectDialog({ onSubmit, onCancel }) {
  const [form, setForm] = useState({ name: '', plcType: 'S7-1200', tiaVersion: 'V18', language: 'SCL' })
  const set = (key, val) => setForm(f => ({ ...f, [key]: val }))

  const handleSubmit = () => {
    if (!form.name.trim()) return
    onSubmit(form)
  }

  const selectClass = "w-full bg-ide-input border border-ide-border rounded px-2 py-1.5 text-xs text-text-primary outline-none focus:border-accent"

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onCancel}>
      <div className="bg-ide-panel border border-ide-border rounded-lg p-5 w-[360px] shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-2 mb-4">
          <FolderPlus size={16} className="text-accent" />
          <h3 className="text-sm font-medium text-text-bright">新建项目</h3>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-2xs text-text-dim block mb-1">项目名称</label>
            <input autoFocus type="text" value={form.name} onChange={e => set('name', e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleSubmit(); if (e.key === 'Escape') onCancel() }}
              placeholder="例: 包装线控制系统"
              className="w-full bg-ide-input border border-ide-border rounded px-3 py-2 text-sm text-text-primary placeholder-text-dim outline-none focus:border-accent" />
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="text-2xs text-text-dim block mb-1">PLC 型号</label>
              <select value={form.plcType} onChange={e => set('plcType', e.target.value)}
                style={{ color: '#CCC', backgroundColor: '#2D2D2D' }} className={selectClass}>
                {PLC_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="text-2xs text-text-dim block mb-1">TIA 版本</label>
              <select value={form.tiaVersion} onChange={e => set('tiaVersion', e.target.value)}
                style={{ color: '#CCC', backgroundColor: '#2D2D2D' }} className={selectClass}>
                {TIA_VERSIONS.map(v => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>
            <div>
              <label className="text-2xs text-text-dim block mb-1">编程语言</label>
              <select value={form.language} onChange={e => set('language', e.target.value)}
                style={{ color: '#CCC', backgroundColor: '#2D2D2D' }} className={selectClass}>
                {LANGUAGES.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onCancel}
            className="px-3 py-1.5 text-xs text-text-dim hover:text-text-primary border border-ide-border rounded transition-colors">
            取消
          </button>
          <button onClick={handleSubmit} disabled={!form.name.trim()}
            className="px-4 py-1.5 text-xs bg-accent text-white rounded font-medium hover:bg-accent-hover disabled:opacity-30 transition-colors">
            创建项目
          </button>
        </div>
      </div>
    </div>
  )
}
