import { useState, useEffect, useRef } from 'react'
import { listTemplates, getTemplateCategories } from '../api'
import useEscClose from '../hooks/useEscClose'
import useFocusTrap from '../hooks/useFocusTrap'

export default function PromptTemplateModal({ onClose, onSelect }) {
  const [templates, setTemplates] = useState([])
  const containerRef = useRef(null)
  const [categories, setCategories] = useState([])
  const [activeCat, setActiveCat] = useState('')
  const [selected, setSelected] = useState(null)
  const [varValues, setVarValues] = useState({})

  // Batch 8：Esc 关闭弹窗（主计划 §11.4）
  useEscClose(onClose)
  // F-015：焦点锁定
  useFocusTrap(containerRef, true)

  useEffect(() => {
    getTemplateCategories().then((d) => setCategories(d.categories || [])).catch(() => {})
    loadTemplates()
  }, [])

  const loadTemplates = async (cat = '') => {
    try {
      const d = await listTemplates(cat)
      setTemplates(d.templates || [])
    } catch { setTemplates([]) }
  }

  const handleCatClick = (cat) => {
    const next = cat === activeCat ? '' : cat
    setActiveCat(next)
    loadTemplates(next)
  }

  const handleTemplateClick = (t) => {
    setSelected(t)
    const init = {}
    ;(t.variables || []).forEach((v) => { init[v.name] = v.default })
    setVarValues(init)
  }

  const handleUseTemplate = () => {
    if (!selected) return
    let content = selected.content
    Object.entries(varValues).forEach(([k, v]) => {
      content = content.replace(`{${k}}`, v)
    })
    onSelect(content)
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/90 flex items-center justify-center z-50">
      <div ref={containerRef} className="bg-surface w-[700px] max-h-[80vh] rounded-xl border border-surface-border shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-surface-border">
          <h2 className="text-text-primary font-semibold">📋 Prompt 模板</h2>
          <button onClick={onClose} className="text-text-dim hover:text-text-primary text-lg">✕</button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Categories sidebar */}
          <div className="w-36 border-r border-surface-border p-2 space-y-0.5 overflow-y-auto shrink-0">
            <button
              onClick={() => { setActiveCat(''); loadTemplates('') }}
              className={`w-full text-left px-2 py-1.5 rounded text-xs transition-colors ${
                !activeCat ? 'bg-accent/15 text-accent' : 'text-text-secondary hover:bg-surface-hover'
              }`}
            >
              全部 ({templates.length})
            </button>
            {categories.map((c) => (
              <button
                key={c.name}
                onClick={() => handleCatClick(c.name)}
                className={`w-full text-left px-2 py-1.5 rounded text-xs transition-colors ${
                  activeCat === c.name ? 'bg-accent/15 text-accent' : 'text-text-secondary hover:bg-surface-hover'
                }`}
              >
                {c.name} ({c.count})
              </button>
            ))}
          </div>

          {/* Main content */}
          <div className="flex-1 flex overflow-hidden">
            {/* Template list */}
            <div className="w-56 border-r border-surface-border overflow-y-auto p-2 space-y-1">
              {templates.map((t) => (
                <button
                  key={t.id}
                  onClick={() => handleTemplateClick(t)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors ${
                    selected?.id === t.id
                      ? 'bg-accent/15 border border-accent/30'
                      : 'bg-surface-alt border border-transparent hover:border-surface-border'
                  }`}
                >
                  <div className="font-medium text-text-primary mb-0.5">{t.name}</div>
                  <div className="text-text-dim truncate">{t.description || t.category}</div>
                </button>
              ))}
            </div>

            {/* Template detail */}
            <div className="flex-1 flex flex-col overflow-hidden">
              {selected ? (
                <div className="flex-1 overflow-y-auto p-3 space-y-3">
                  <div>
                    <div className="text-xs font-medium text-accent mb-1">{selected.category}</div>
                    <h3 className="text-sm font-semibold text-text-primary">{selected.name}</h3>
                    <p className="text-xs text-text-dim mt-1">{selected.description}</p>
                  </div>

                  {/* Variables */}
                  {selected.variables?.length > 0 && (
                    <div className="bg-surface-alt rounded-lg p-3 space-y-2">
                      <div className="text-xs font-medium text-text-secondary">变量设置</div>
                      {selected.variables.map((v) => (
                        <div key={v.name} className="flex items-center gap-2">
                          <label className="text-xs text-text-dim w-28 shrink-0">{v.label}</label>
                          <input
                            type={v.type === 'int' ? 'number' : 'text'}
                            value={varValues[v.name] || ''}
                            onChange={(e) => setVarValues({ ...varValues, [v.name]: e.target.value })}
                            className="flex-1 bg-surface border border-surface-border rounded px-2 py-1 text-xs text-text-primary outline-none focus:border-accent/50"
                          />
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Content preview */}
                  <div>
                    <div className="text-xs font-medium text-text-secondary mb-1">模板内容</div>
                    <pre className="bg-surface-alt rounded-lg p-3 text-xs text-text-secondary leading-relaxed whitespace-pre-wrap font-mono max-h-48 overflow-y-auto">
                      {selected.content}
                    </pre>
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex items-center justify-center text-text-dim text-xs">
                  选择一个模板查看详情
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        {selected && (
          <div className="flex justify-end gap-2 px-5 py-3 border-t border-surface-border">
            <button onClick={onClose} className="px-4 py-1.5 text-xs text-text-secondary hover:text-text-primary transition-colors">
              取消
            </button>
            <button
              onClick={handleUseTemplate}
              className="px-4 py-1.5 text-xs bg-accent/20 text-accent rounded-lg hover:bg-accent/30 transition-colors"
            >
              使用此模板
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
