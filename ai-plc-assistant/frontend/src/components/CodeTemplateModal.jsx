import { useState, useEffect } from 'react'
import { listCodeTemplates, getCodeTemplateContent } from '../api'

function IoTable({ title, signals }) {
  if (!signals || signals.length === 0) return null
  return (
    <div className="mb-3">
      <div className="text-2xs font-semibold text-text-dim mb-1 uppercase tracking-wider">{title}</div>
      <div className="space-y-0.5">
        {signals.map((s, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="text-text-primary font-medium">{s.comment || s.name}</span>
            <span className="text-2xs text-text-dim bg-surface-alt px-1 rounded">{s.type}</span>
            <span className="text-2xs text-text-dim">({s.name})</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function CodeTemplateModal({ onClose }) {
  const [templates, setTemplates] = useState([])
  const [selected, setSelected] = useState(null)
  const [content, setContent] = useState('')
  const [ioData, setIoData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [showScl, setShowScl] = useState(true)

  useEffect(() => {
    listCodeTemplates().then(d => setTemplates(d.templates || [])).catch(() => {})
  }, [])

  const handleSelect = async (t) => {
    setSelected(t)
    setLoading(true)
    setIoData(null)
    try {
      const data = await getCodeTemplateContent(t.name)
      setContent(data.content || '')
      if (data.io) setIoData(data.io)
    } catch { setContent('// 加载失败') }
    setLoading(false)
  }

  const sclTemplates = templates.filter(t => t.type === 'scl')
  const docTemplates = templates.filter(t => t.type === 'md')

  return (
    <div className="fixed inset-0 bg-black/90 flex items-center justify-center z-50">
      <div className="bg-surface w-[800px] max-h-[85vh] rounded-xl border border-surface-border shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-surface-border">
          <h2 className="text-text-primary font-semibold">SCL 代码模板</h2>
          <div className="flex items-center gap-3">
            <div className="flex bg-surface-alt rounded-lg p-0.5 text-xs">
              <button onClick={() => setShowScl(true)}
                className={`px-2.5 py-1 rounded-md transition-colors ${showScl ? 'bg-accent/20 text-accent' : 'text-text-dim hover:text-text-secondary'}`}>
                SCL ({sclTemplates.length})
              </button>
              <button onClick={() => setShowScl(false)}
                className={`px-2.5 py-1 rounded-md transition-colors ${!showScl ? 'bg-accent/20 text-accent' : 'text-text-dim hover:text-text-secondary'}`}>
                文档 ({docTemplates.length})
              </button>
            </div>
            <button onClick={onClose} className="text-text-dim hover:text-text-primary text-lg">✕</button>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden min-h-[400px]">
          {/* Template list */}
          <div className="w-56 border-r border-surface-border overflow-y-auto p-2 space-y-1">
            {(showScl ? sclTemplates : docTemplates).map((t) => (
              <button
                key={t.name}
                onClick={() => handleSelect(t)}
                className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors ${
                  selected?.name === t.name
                    ? 'bg-accent/15 border border-accent/30'
                    : 'bg-surface-alt border border-transparent hover:border-surface-border'
                }`}
              >
                <div className="font-medium text-text-primary mb-0.5">{t.title || t.name}</div>
                <div className="text-text-dim text-2xs">{t.type.toUpperCase()} · {t.name}.{t.type}</div>
              </button>
            ))}
            {templates.length === 0 && (
              <div className="text-text-dim text-xs text-center py-8">暂无模板</div>
            )}
          </div>

          {/* Code display */}
          <div className="flex-1 overflow-auto">
            {loading ? (
              <div className="flex items-center justify-center h-full text-text-dim text-xs">加载中...</div>
            ) : content ? (
              <div className="p-4">
                {/* IO 表（仅 SCL 代码展示） */}
                {ioData && selected?.type === 'scl' && (
                  <div className="mb-4 p-3 bg-surface-alt rounded-lg border border-surface-border">
                    <div className="text-xs font-semibold text-text-primary mb-2">接口信号（中文）</div>
                    <IoTable title="输入" signals={ioData.inputs} />
                    <IoTable title="输出" signals={ioData.outputs} />
                    <IoTable title="输入输出" signals={ioData.inouts} />
                  </div>
                )}
                <pre className="text-xs text-text-primary font-mono leading-relaxed whitespace-pre-wrap overflow-x-auto">{content}</pre>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-text-dim text-xs">选择一个模板查看代码</div>
            )}
          </div>
        </div>

        {/* Footer */}
        {content && (
          <div className="flex justify-end items-center gap-2 px-5 py-3 border-t border-surface-border">
            <span className="text-2xs text-text-dim flex-1">{selected?.name}.{selected?.type}</span>
            <button onClick={() => { navigator.clipboard.writeText(content) }}
              className="px-3 py-1 text-xs bg-surface-alt border border-surface-border rounded-lg hover:border-accent/40 text-text-secondary hover:text-accent transition-colors">
              复制代码
            </button>
            <button onClick={onClose}
              className="px-3 py-1 text-xs bg-accent/20 text-accent rounded-lg hover:bg-accent/30 transition-colors">
              关闭
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
