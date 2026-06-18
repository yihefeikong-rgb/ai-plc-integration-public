import { useState, useEffect } from 'react'
import { listLadderTemplates, getLadderTemplate } from '../api'

export default function LadderTemplateModal({ onClose, onUseTemplate }) {
  const [templates, setTemplates] = useState([])
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    listLadderTemplates().then(d => setTemplates(d.templates || [])).catch(() => {})
  }, [])

  const handleSelect = async (t) => {
    setSelected(t)
    setLoading(true)
    try {
      const data = await getLadderTemplate(t.name)
      setDetail(data)
    } catch { setDetail(null) }
    setLoading(false)
  }

  const handleUse = () => {
    if (!selected || !detail) return
    const prompt = `请基于「${selected.name}」梯形图模板，为我生成PLC程序并写入TIA Portal。\n\n模板信息：\n${detail.text}`
    onUseTemplate?.(prompt)
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-surface w-[850px] max-h-[85vh] rounded-xl border border-surface-border shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-surface-border">
          <h2 className="text-text-primary font-semibold">梯形图模板库</h2>
          <div className="flex items-center gap-2">
            <span className="text-2xs text-text-dim bg-surface-alt px-2 py-0.5 rounded">
              {templates.length} 个模板
            </span>
            <button onClick={onClose} className="text-text-dim hover:text-text-primary text-lg">✕</button>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden min-h-[450px]">
          {/* Template list */}
          <div className="w-52 border-r border-surface-border overflow-y-auto p-2 space-y-1">
            {templates.map((t) => (
              <button
                key={t.name}
                onClick={() => handleSelect(t)}
                className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors ${
                  selected?.name === t.name
                    ? 'bg-accent/15 border border-accent/30'
                    : 'bg-surface-alt border border-transparent hover:border-surface-border'
                }`}
              >
                <div className="font-medium text-text-primary mb-0.5">{t.name}</div>
                <div className="text-text-dim text-2xs">
                  {t.inputCount}入 {t.outputCount}出 · {t.networkCount}段
                </div>
              </button>
            ))}
            {templates.length === 0 && (
              <div className="text-text-dim text-xs text-center py-8">加载中...</div>
            )}
          </div>

          {/* Detail display */}
          <div className="flex-1 overflow-auto">
            {loading ? (
              <div className="flex items-center justify-center h-full text-text-dim text-xs">加载中...</div>
            ) : detail ? (
              <pre className="p-4 text-xs text-text-primary font-mono leading-relaxed whitespace-pre-wrap">{detail.text}</pre>
            ) : (
              <div className="flex items-center justify-center h-full text-text-dim text-xs">
                ← 选择一个梯形图模板查看详情
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        {detail && (
          <div className="flex justify-between items-center px-5 py-3 border-t border-surface-border">
            <span className="text-2xs text-text-dim">
              {selected?.name} · {selected?.blockName}
            </span>
            <div className="flex gap-2">
              <button onClick={() => { navigator.clipboard.writeText(JSON.stringify(detail.data, null, 2)) }}
                className="px-3 py-1 text-xs bg-surface-alt border border-surface-border rounded-lg hover:border-accent/40 text-text-secondary hover:text-accent transition-colors">
                复制JSON
              </button>
              <button onClick={handleUse}
                className="px-3 py-1 text-xs bg-accent text-white rounded-lg hover:bg-accent/80 transition-colors font-medium">
                使用模板 →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
