import { useState } from 'react'
import { Play, Loader2, Code2, Download, FileCode, FileText as FileXml, Table2, Clock } from 'lucide-react'
import { generateLadder, exportCode } from '../api'
import useWorkbenchHistory from '../hooks/useWorkbenchHistory'

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
  const { history, save } = useWorkbenchHistory('ladder-generator')

  const handleGenerate = async () => {
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

  const { structured, title, description: desc, mode } = result || {}
  const { variables, networks } = structured || {}

  return (
    <div className="flex-1 flex overflow-hidden bg-ide-bg">
      {/* Left: Input */}
      <div className="w-[400px] flex flex-col border-r border-ide-border shrink-0">
        <div className="flex items-center gap-2 px-4 py-2 border-b border-ide-border bg-ide-panel">
          <Code2 size={15} className="text-accent" />
          <span className="text-xs text-text-primary font-medium">梯形图生成</span>
          <div className="flex-1" />
          {history.length > 0 && (
            <select onChange={e => { const h = history.find(x => x.id === e.target.value); if (h) { setDescription(h.description); setResult(h.result) } }} value=""
              style={{ color: '#CCC', backgroundColor: '#3C3C3C' }}
              className="border border-ide-border rounded px-2 py-1 text-2xs outline-none">
              <option value="">历史 ({history.length})</option>
              {history.map(h => <option key={h.id} value={h.id}>{h.time} — {h.label}...</option>)}
            </select>
          )}
        </div>
        <div className="p-4 flex-1 flex flex-col gap-3">
          <label className="text-xs text-text-dim">控制需求描述</label>
          <textarea value={description} onChange={e => setDescription(e.target.value)}
            placeholder={"描述你需要的控制程序...\n\n示例:\n- 电机正反转控制，带互锁和过载保护\n- 十字路口交通灯，绿灯30秒黄灯3秒\n- 传送带启停，带光电传感器检测"}
            className="flex-1 bg-ide-bg border border-ide-border rounded p-3 text-xs text-text-primary placeholder-text-dim outline-none focus:border-accent resize-none"
            spellCheck={false} />
          <button onClick={handleGenerate} disabled={loading || !description.trim()}
            className="flex items-center justify-center gap-2 px-4 py-2 bg-accent text-white rounded text-xs font-medium hover:bg-accent-hover disabled:opacity-30 transition-colors">
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {loading ? '生成中...' : '生成梯形图'}
          </button>
        </div>
      </div>

      {/* Right: Result */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-2 border-b border-ide-border bg-ide-panel">
          <span className="text-xs text-text-primary font-medium">生成结果</span>
          {mode && <span className="text-2xs text-text-dim ml-auto">模式: {mode}</span>}
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {result ? (
            <div className="space-y-4">
              {/* Title */}
              <div>
                <div className="text-sm font-medium text-accent">{title}</div>
                {desc && <div className="text-2xs text-text-dim mt-1">{desc}</div>}
              </div>

              {/* Variable Table */}
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

              {/* Networks */}
              {networks?.length > 0 && (
                <div className="space-y-2">
                  <div className="text-2xs font-medium text-text-secondary uppercase tracking-wider">程序逻辑</div>
                  {networks.map((n, i) => (
                    <div key={i} className="border border-ide-border rounded overflow-hidden">
                      <div className="px-3 py-1.5 bg-ide-panel border-b border-ide-border flex items-center gap-2">
                        <span className="text-2xs font-mono text-accent">Network {n.number}</span>
                        <span className="text-xs text-text-primary">{n.title}</span>
                      </div>
                      {n.comment && <div className="px-3 py-1 text-2xs text-text-dim border-b border-ide-border">// {n.comment}</div>}
                      {n.code && (
                        <pre className="px-3 py-2 text-xs text-text-secondary font-mono leading-relaxed overflow-x-auto bg-ide-panel">{n.code}</pre>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Export */}
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
              {loading ? <><Loader2 size={16} className="animate-spin mr-2" /> 生成中...</> : '在左侧描述控制需求，点击「生成梯形图」'}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
