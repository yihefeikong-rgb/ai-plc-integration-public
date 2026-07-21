import { useState, useRef, useEffect } from 'react'
import { Play, Loader2, AlertTriangle, Copy, Check, Clock } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { streamChat } from '../api'
import useWorkbenchHistory from '../hooks/useWorkbenchHistory'
import { ToolStatusBar } from './ui'

const DIAG_PROMPT = (plcType) => `你是一名资深的西门子PLC工程师和工业自动化故障诊断专家。
当前PLC型号：${plcType}

请根据以下故障描述进行系统诊断，按以下结构回答：

## 故障概述
简要复述故障现象。

## 可能原因（按概率排序）
1. **最可能原因** — 详细说明
2. **次可能原因** — 详细说明
3. ...

## 排查步骤
按优先级给出具体操作步骤，每步包含：
- 检查什么
- 用什么工具/方法
- 预期结果
- 如果异常怎么处理

## 相关诊断缓冲区
列出可能有用的 TIA Portal 诊断缓冲区内容和 LED 状态含义。

## 预防措施
给出避免此故障再次发生的建议。

故障描述：
`

const PLC_TYPES = ['S7-1200', 'S7-1500', 'S7-300', 'S7-400', 'S7-200 SMART']

export default function FaultDiagnosis({ addLog, selectedModel = 'deepseek' }) {
  const [symptoms, setSymptoms] = useState('')
  const [plcType, setPlcType] = useState('S7-1200')
  const [errorCode, setErrorCode] = useState('')
  const [result, setResult] = useState('')
  // P3 状态机改造：loading: boolean → status: 10 种状态
  const [status, setStatus] = useState('idle')
  const [statusMessage, setStatusMessage] = useState('')
  const [copied, setCopied] = useState(false)
  const { history, save } = useWorkbenchHistory('fault-diagnosis')
  const loading = status === 'running'
  // F-043 修复：组件卸载时 abort 进行中的 streamChat
  const abortRef = useRef(null)
  useEffect(() => () => abortRef.current?.abort(), [])

  const handleDiagnose = async () => {
    if (!symptoms.trim() || loading) return
    setStatus('running')
    setStatusMessage('AI 正在诊断故障...')
    setResult('')
    addLog?.('info', `[故障诊断] ${plcType}: ${symptoms.slice(0, 50)}...`)
    let fullResult = ''
    // F-043：传 signal 支持卸载时取消；重入时先 abort 前一个请求
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    let input = symptoms
    if (errorCode.trim()) input += `\n\n错误代码: ${errorCode}`

    try {
      await streamChat({
        model_id: selectedModel,
        messages: [{ role: 'user', content: DIAG_PROMPT(plcType) + input }],
        temperature: 0.3,
        signal: controller.signal,
        onToken: (token) => { fullResult += token; setResult(prev => prev + token) },
        onDone: (data) => {
          save({ label: symptoms.slice(0, 40), symptoms, plcType, errorCode, result: fullResult })
          if (data?.fallback) {
            addLog?.('warn', `[故障诊断] 已切换到 ${data.model}`)
            setStatus('model_unavailable')
            setStatusMessage(`主模型不可用，已切换到 ${data.model}`)
          } else {
            setStatus(fullResult ? 'success' : 'no_result')
            setStatusMessage(fullResult ? '诊断完成' : '诊断完成但无内容')
          }
          addLog?.('info', '[故障诊断] 完成')
        },
        onError: (err) => {
          setResult(prev => prev || `诊断失败: ${err.message}`)
          addLog?.('error', `[故障诊断] ${err.message}`)
          setStatus('failed')
          setStatusMessage(err.message)
        },
      })
    } catch (err) {
      setResult(`诊断失败: ${err.message}`)
      addLog?.('error', `[故障诊断] ${err.message}`)
      const isOffline = /Failed to fetch|NetworkError|network/i.test(err.message)
      setStatus(isOffline ? 'offline' : 'failed')
      setStatusMessage(err.message)
    }
  }

  return (
    <div className="flex-1 flex overflow-hidden bg-ide-bg">
      {/* Left: Input */}
      <div className="w-[400px] flex flex-col border-r border-ide-border shrink-0">
        <div className="flex items-center gap-2 px-4 py-2 border-b border-ide-border bg-ide-panel">
          <AlertTriangle size={15} className="text-status-warn" />
          <span className="text-xs text-text-primary font-medium">故障诊断</span>
          <div className="flex-1" />
          {history.length > 0 && (
            <select onChange={e => { const h = history.find(x => x.id === e.target.value); if (h) { setSymptoms(h.symptoms); setPlcType(h.plcType || 'S7-1200'); setErrorCode(h.errorCode || ''); setResult(h.result) } }} value=""
              style={{ color: '#CCC', backgroundColor: '#3C3C3C' }}
              className="border border-ide-border rounded px-2 py-1 text-2xs outline-none">
              <option value="">历史 ({history.length})</option>
              {history.map(h => <option key={h.id} value={h.id}>{h.time} — {h.label}...</option>)}
            </select>
          )}
        </div>

        <div className="p-4 flex-1 flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <label className="text-xs text-text-dim w-16 shrink-0">PLC 型号</label>
            <select value={plcType} onChange={e => setPlcType(e.target.value)}
              style={{ color: '#CCC', backgroundColor: '#3C3C3C' }}
              className="flex-1 border border-ide-border rounded px-2 py-1.5 text-xs outline-none focus:border-accent">
              {PLC_TYPES.map(t => <option key={t} value={t} style={{ color: '#CCC', backgroundColor: '#3C3C3C' }}>{t}</option>)}
            </select>
          </div>

          <div className="flex items-center gap-3">
            <label className="text-xs text-text-dim w-16 shrink-0">错误代码</label>
            <input type="text" value={errorCode} onChange={e => setErrorCode(e.target.value)}
              placeholder="可选，如 16#8104"
              className="flex-1 bg-ide-input border border-ide-border rounded px-2 py-1.5 text-xs text-text-primary placeholder-text-dim outline-none focus:border-accent font-mono" />
          </div>

          <label className="text-xs text-text-dim">故障描述</label>
          <textarea
            value={symptoms}
            onChange={e => setSymptoms(e.target.value)}
            placeholder={'描述故障现象...\n\n示例:\nS7-1200 运行中突然停机，RUN/STOP LED 闪烁红色，\n诊断缓冲区显示「看门狗超时」。\n程序中有一个 FC 处理 Modbus 通信，\n最近修改过该 FC 的超时参数。'}
            className="flex-1 bg-ide-bg border border-ide-border rounded p-3 text-xs text-text-primary placeholder-text-dim outline-none focus:border-accent resize-none"
            spellCheck={false}
          />

          <button onClick={handleDiagnose} disabled={loading || !symptoms.trim()}
            className="flex items-center justify-center gap-2 px-4 py-2 bg-accent text-white rounded text-xs font-medium hover:bg-accent-hover disabled:opacity-30 transition-colors">
            {loading ? <Loader2 size={14} className="animate-spin" /> : <AlertTriangle size={14} />}
            {loading ? '诊断中...' : '开始诊断'}
          </button>
        </div>
      </div>

      {/* Right: Result */}
      <div className="flex-1 flex flex-col">
        <div className="flex items-center gap-2 px-4 py-2 border-b border-ide-border bg-ide-panel">
          <span className="text-xs text-text-primary font-medium">诊断结果</span>
          <div className="flex-1" />
          {result && (
            <button onClick={() => { navigator.clipboard.writeText(result); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
              className="flex items-center gap-1 px-2 py-0.5 text-2xs text-text-dim hover:text-text-primary border border-ide-border rounded">
              {copied ? <Check size={11} /> : <Copy size={11} />}
              {copied ? '已复制' : '复制'}
            </button>
          )}
        </div>

        {/* P3：统一状态栏（10 种状态）*/}
        <ToolStatusBar status={status} message={statusMessage} model={selectedModel} />
        <div className="flex-1 overflow-y-auto p-4">
          {result ? (
            <div className="prose prose-invert max-w-none prose-sm text-text-primary
                            prose-headings:text-text-bright prose-h2:text-sm prose-h2:border-b prose-h2:border-ide-border prose-h2:pb-1
                            prose-strong:text-status-warn prose-code:text-accent">
              <ReactMarkdown>{result}</ReactMarkdown>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-text-dim text-xs">
              {loading ? <><Loader2 size={16} className="animate-spin mr-2" /> 分析中...</> : '在左侧描述故障现象，点击「开始诊断」'}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
