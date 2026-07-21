import { useState, useRef, useEffect } from 'react'
import { Play, Loader2, Code2, Download, FileCode, FileText as FileXml, Table2, Eye, FileText, Send } from 'lucide-react'
import { generateLadder, exportCode, runNlToSim } from '../api'
import useWorkbenchHistory from '../hooks/useWorkbenchHistory'
import LadderVisualizer from './LadderVisualizer'
import { ToolStatusBar } from './ui'

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

export default function LadderGenerator({ addLog, selectedModel = 'deepseek' }) {
  const [description, setDescription] = useState('')
  const [result, setResult] = useState(null)
  // P3 状态机改造：loading: boolean → status: 10 种状态
  const [status, setStatus] = useState('idle')
  const [statusMessage, setStatusMessage] = useState('')
  // pipeline 独立状态机（与 generate 并行）
  const [pipelineStatus, setPipelineStatus] = useState('idle')
  const [pipelineStatusMessage, setPipelineStatusMessage] = useState('')
  const [pipelineResult, setPipelineResult] = useState(null)
  const [displayMode, setDisplayMode] = useState('graph')
  const { history, save } = useWorkbenchHistory('ladder-generator')
  const resultRef = useRef(null)
  const loading = status === 'running'
  const pipelineLoading = pipelineStatus === 'running'

  const handleGenerate = async (e) => {
    e?.preventDefault?.()
    if (!description.trim() || loading) return
    setStatus('running')
    setStatusMessage('AI 正在生成梯形图...')
    setResult(null)
    setPipelineResult(null)
    addLog?.('info', `[梯形图] 生成: ${description.slice(0, 50)}...`)

    try {
      const data = await generateLadder(description, {}, '', selectedModel)
      setResult(data)
      save({ label: description.slice(0, 40), description, result: data })
      addLog?.('info', `[梯形图] ${data.title} (${data.mode})`)
      // 判定结果状态：有 networks 为 success，无 networks 为 no_result
      const hasNetworks = data.structured?.networks?.length > 0
      setStatus(hasNetworks ? 'success' : 'no_result')
      setStatusMessage(hasNetworks ? `生成完成：${data.title}` : '生成完成但无 Network')
    } catch (err) {
      addLog?.('error', `[梯形图] ${err.message}`)
      const isOffline = /Failed to fetch|NetworkError|network/i.test(err.message)
      setStatus(isOffline ? 'offline' : 'failed')
      setStatusMessage(err.message)
    }
  }

  const handleRunPipeline = async () => {
    if (!description.trim() || loading || pipelineLoading) return
    setPipelineStatus('running')
    setPipelineStatusMessage('全链路执行中：生成→编译→下载→回读...')
    setPipelineResult(null)
    addLog?.('info', `[全链路] 生成并仿真: ${description.slice(0, 50)}...`)

    try {
      const data = await runNlToSim({ description, launch_fio: false })
      setPipelineResult(data)
      addLog?.(data.ok ? 'info' : 'error', `[全链路] ${data.ok ? 'PASS' : 'FAIL'}${data.error ? `: ${data.error}` : ''}`)
      // 判定 pipeline 状态：ok=true 为 success，部分步骤 FAIL 为 partial，全部 FAIL 为 failed
      const steps = data.steps || []
      const hasPass = steps.some((s) => s.status === 'PASS')
      const hasFail = steps.some((s) => s.status === 'FAIL')
      if (data.ok) {
        setPipelineStatus('success')
        setPipelineStatusMessage('全链路 PASS')
      } else if (hasPass && hasFail) {
        setPipelineStatus('partial')
        setPipelineStatusMessage('部分步骤失败')
      } else {
        setPipelineStatus('failed')
        setPipelineStatusMessage(data.error || '全链路失败')
      }
    } catch (err) {
      const failed = { ok: false, error: err.message, steps: [], snap7: { verified: false, readback: '' }, generation: {} }
      setPipelineResult(failed)
      addLog?.('error', `[全链路] ${err.message}`)
      const isOffline = /Failed to fetch|NetworkError|network/i.test(err.message)
      setPipelineStatus(isOffline ? 'offline' : 'failed')
      setPipelineStatusMessage(err.message)
    }
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

      {/* P3：统一状态栏（generate + pipeline 双状态）*/}
      {/* P3-LOW-01 修复：pipeline 完成后（非 idle）仍显示 pipeline 状态，避免切回 generate 隐藏最终结果 */}
      <ToolStatusBar
        status={pipelineStatus !== 'idle' ? pipelineStatus : status}
        message={pipelineStatus !== 'idle' ? pipelineStatusMessage : statusMessage}
        model={selectedModel}
      />

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

            {pipelineResult && <PipelinePanel result={pipelineResult} />}
          </div>
        ) : pipelineResult ? (
          <div className="max-w-4xl mx-auto">
            <PipelinePanel result={pipelineResult} />
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-text-dim text-xs">
            {loading || pipelineLoading ? <><Loader2 size={16} className="animate-spin mr-2" /> {pipelineLoading ? '全链路执行中...' : '生成中...'}</> : '输入控制需求描述，点击发送生成梯形图'}
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
            disabled={loading || pipelineLoading}
          />
          <button
            type="button"
            onClick={handleRunPipeline}
            disabled={loading || pipelineLoading || !description.trim()}
            className="flex items-center gap-1.5 px-4 py-2 bg-ide-panel border border-accent/50 text-accent rounded text-xs font-medium hover:bg-accent/10 disabled:opacity-30 transition-colors"
          >
            {pipelineLoading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {pipelineLoading ? '仿真中' : '生成并仿真'}
          </button>
          <button
            type="submit"
            disabled={loading || pipelineLoading || !description.trim()}
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

function PipelinePanel({ result }) {
  const steps = result.steps || []
  const statusClass = result.ok ? 'text-green-400' : 'text-red-400'

  return (
    <div className="border border-ide-border rounded bg-ide-panel overflow-hidden">
      <div className="px-3 py-2 border-b border-ide-border flex items-center gap-2">
        <Play size={13} className={statusClass} />
        <span className="text-xs font-medium text-text-primary">全链路验证</span>
        <span className={`text-2xs ml-auto ${statusClass}`}>{result.ok ? 'PASS' : 'FAIL'}</span>
      </div>
      <div className="p-3 space-y-3">
        {result.error && (
          <div className="text-xs text-red-300 bg-red-950/30 border border-red-900/40 rounded px-3 py-2">
            {result.error}
          </div>
        )}

        {result.generation?.block_name && (
          <div className="text-2xs text-text-secondary">
            生成块: <span className="font-mono text-accent">{result.generation.block_name}</span>
          </div>
        )}

        <div className="space-y-1.5">
          {steps.map((step, index) => (
            <div key={`${step.name}-${index}`} className="flex items-start gap-2 text-xs border border-ide-border rounded px-2 py-1.5 bg-ide-bg">
              <span className={step.status === 'PASS' ? 'text-green-400' : step.status === 'FAIL' ? 'text-red-400' : 'text-text-dim'}>
                {step.status || 'PENDING'}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-text-primary">{step.name}</div>
                {step.detail && <div className="text-2xs text-text-dim mt-0.5 break-words">{formatDetail(step.detail)}</div>}
              </div>
            </div>
          ))}
        </div>

        {result.snap7?.readback && (
          <div className="text-2xs text-text-secondary">
            snap7 回读: <span className="font-mono text-accent">{result.snap7.readback}</span>
          </div>
        )}
      </div>
    </div>
  )
}

function formatDetail(detail) {
  if (typeof detail === 'string') return detail
  try {
    return JSON.stringify(detail)
  } catch {
    return String(detail)
  }
}
