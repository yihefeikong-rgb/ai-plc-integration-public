import { useState, useRef, useEffect } from 'react'
import { Play, Loader2, Code2, Download, FileCode, FileText as FileXml, Table2, Eye, FileText, Send } from 'lucide-react'
import { generateLadder, exportCode } from '../api'
import useWorkbenchHistory from '../hooks/useWorkbenchHistory'
import LadderVisualizer from './LadderVisualizer'

function downloadFile(content, filename, mime = 'text/plain') {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

async function doExport(structured, format, title) {
  try {
    const data = await exportCode({
      title: title || 'export',
      variables: structured.variables || [],
      networks: structured.networks || [],
      format, block_type: 'FB', block_name: title || 'GeneratedBlock',
    })
    downloadFile(data.content, data.filename, data.mime_type)
  } catch (err) { alert('导出失败: ' + err.message) }
}

export default function LadderGenerator({ addLog }) {
  const [description, setDescription] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [displayMode, setDisplayMode] = useState('graph')
  const { history, save } = useWorkbenchHistory('ladder-generator')
  const resultRef = useRef(null)

  const handleGenerate = async (e) => {
    e?.preventDefault?.()
    if (!description.trim() || loading) return
    setLoading(true)
    setResult(null)
    addLog?.('info', `[梯形图] 生成: ${description.slice(0, 50)}...`)

    try {
      const data = await generateLadder(description, {}, '', 'deepseek')
      setResult(data)
      save({ label: description.slice(0, 40), description, result: data })
      addLog?.('info', `[梯形图] ${data.title} (${data.mode})`)
    } catch (err) {
      addLog?.('error', `[梯形图] ${err.message}`)
    }
    setLoading(false)
  }

  // 生成结果后自动滚到顶部
  useEffect(() => {
    if (result && resultRef.current) resultRef.current.scrollTop = 0
  }, [result])

  const { structured, title, description: desc, mode, text: rawText } = result || {}
  const { variables, networks } = structured || {}

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-ide-bg">
      {/* ── 标题栏 ── */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-ide-border bg-ide-panel">
        <Code2 size={15} className="text-accent" />
        <span className="text-xs text-text-primary font-medium">梯形图生成</span>
        <div className="flex-1" />
        {mode && <span className="text-2xs text-text-dim">模式: {mode}</span>}
        {/* 图形 / 源码 切换 */}
        {result && (
          <div className="flex items-center gap-1 ml-2">
            {[
              { key: 'graph', icon: Eye, label: '图形' },
              { key: 'source', icon: FileText, label: '源码' },
            ].map(({ key, label, icon: Icon }) => (
              <button key={key}
                onClick={() => setDisplayMode(key)}
                className={`flex items-center gap-1 px-2 py-0.5 text-2xs rounded transition-colors ${
                  displayMode === key
                    ? 'bg-accent text-white'
                    : 'bg-ide-panel border border-ide-border text-text-secondary hover:border-accent/40'
                }`}>
                <Icon size={11} />
                {label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── 历史记录（标题栏下方） ── */}
      {history.length > 0 && (
        <div className="flex items-center gap-2 px-4 py-1.5 border-b border-ide-border bg-ide-sidebar">
          <span className="text-2xs text-text-dim">历史:</span>
          <select
            onChange={e => {
              const h = history.find(x => x.id === e.target.value)
              if (h) { setDescription(h.description); setResult(h.result) }
            }}
            value=""
            style={{ color: '#CCC', backgroundColor: '#2D2D2D' }}
            className="flex-1 border border-ide-border rounded px-2 py-1 text-2xs outline-none"
          >
            <option value="">选择历史记录 ({history.length})</option>
            {history.map(h => <option key={h.id} value={h.id}>{h.time} — {h.label}...</option>)}
          </select>
        </div>
      )}

      {/* ── 结果区域（可滚动，占满中间） ── */}
      <div ref={resultRef} className="flex-1 overflow-y-auto p-4">
        {result ? (
          <div className="max-w-4xl mx-auto space-y-4">
            {/* 标题 */}
            <div>
              <div className="text-sm font-medium text-accent">{title}</div>
              {desc && <div className="text-2xs text-text-dim mt-1">{desc}</div>}
            </div>

            {/* 变量表 */}
            {variables?.length > 0 && (
              <div>
                <div className="text-2xs font-medium text-text-secondary mb-1 uppercase tracking-wider">变量表</div>
                <div className="overflow-x-auto border border-ide-border rounded">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-ide-panel text-text-dim border-b border-ide-border">
                        <th className="text-left px-3 py-1.5">地址</th>
                        <th className="text-left px-3 py-1.5">符号</th>
                        <th className="text-left px-3 py-1.5">类型</th>
                        <th className="text-left px-3 py-1.5">注释</th>
                      </tr>
                    </thead>
                    <tbody>
                      {variables.map((v, i) => (
                        <tr key={i} className="border-b border-ide-border last:border-0 text-text-secondary">
                          <td className="px-3 py-1 font-mono text-accent">{v.address}</td>
                          <td className="px-3 py-1 font-mono">{v.name}</td>
                          <td className="px-3 py-1">{v.data_type}</td>
                          <td className="px-3 py-1 text-text-dim">{v.comment}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* 图形模式 */}
            {displayMode === 'graph' && networks?.length > 0 && (
              <div>
                <div className="text-2xs font-medium text-text-secondary mb-2 uppercase tracking-wider">程序逻辑</div>
                <LadderVisualizer networks={networks} />
              </div>
            )}

            {/* 源码模式 */}
            {displayMode === 'source' && rawText && (
              <div>
                <div className="text-2xs font-medium text-text-secondary mb-1 uppercase tracking-wider">ASCII-LAD-V2 源码</div>
                <pre className="px-3 py-2 text-xs text-text-secondary font-mono leading-relaxed overflow-x-auto bg-ide-panel border border-ide-border rounded whitespace-pre-wrap">{rawText}</pre>
              </div>
            )}

            {/* 旧格式 code 字段兼容 */}
            {displayMode === 'graph' && (!networks?.length || !networks[0]?.rungs) && networks?.map((n, i) => (
              <div key={i} className="border border-ide-border rounded overflow-hidden">
                <div className="px-3 py-1.5 bg-ide-panel border-b border-ide-border flex items-center gap-2">
                  <span className="text-2xs font-mono text-accent">Network {n.number}</span>
                  <span className="text-xs text-text-primary">{n.title}</span>
                </div>
                {n.comment && <div className="px-3 py-1 text-2xs text-text-dim border-b border-ide-border">// {n.comment}</div>}
                {n.code && <pre className="px-3 py-2 text-xs text-text-secondary font-mono leading-relaxed overflow-x-auto bg-ide-panel">{n.code}</pre>}
              </div>
            ))}

            {/* 导出 */}
            {structured && (
              <div className="flex items-center gap-2 pt-3 border-t border-ide-border">
                <span className="text-2xs text-text-dim mr-1">导出:</span>
                {[
                  { fmt: 'scl', icon: FileCode, label: 'SCL' },
                  { fmt: 'xml', icon: FileXml, label: 'XML' },
                  { fmt: 'csv', icon: Table2, label: 'CSV' },
                  { fmt: 'hmi', icon: Download, label: 'HMI' },
                ].map(({ fmt, icon: Icon, label }) => (
                  <button key={fmt} onClick={() => doExport(structured, fmt, title)}
                    className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent transition-colors text-text-secondary">
                    <Icon size={12} /> {label}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-text-dim text-xs">
            {loading ? <><Loader2 size={16} className="animate-spin mr-2" /> 生成中...</> : '输入控制需求描述，点击发送生成梯形图'}
          </div>
        )}
      </div>

      {/* ── 底部输入栏 ── */}
      <div className="border-t border-ide-border bg-ide-sidebar p-3">
        <form onSubmit={handleGenerate} className="max-w-4xl mx-auto flex gap-2">
          <textarea
            value={description}
            onChange={e => setDescription(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleGenerate(e) } }}
            placeholder="描述控制需求...&#10;例如: 电机正反转控制，带互锁和过载保护&#10;Shift+Enter 换行"
            rows={3}
            className="flex-1 bg-ide-bg border border-ide-border rounded px-3 py-2 text-xs text-text-primary placeholder-text-dim outline-none focus:border-accent resize-none"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !description.trim()}
            className="flex items-center gap-1.5 px-4 py-2 bg-accent text-white rounded text-xs font-medium hover:bg-accent-hover disabled:opacity-30 transition-colors"
          >
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            {loading ? '生成中' : '生成'}
          </button>
        </form>
      </div>
    </div>
  )
}
