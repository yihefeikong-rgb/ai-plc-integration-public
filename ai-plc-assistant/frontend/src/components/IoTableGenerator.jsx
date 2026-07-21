import { useState, useRef, useEffect } from 'react'
import { Play, Loader2, Table2, Copy, Check, Download, Clock } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { streamChat } from '../api'
import useWorkbenchHistory from '../hooks/useWorkbenchHistory'
import { ToolStatusBar } from './ui'

const IO_PROMPT = `你是一名西门子PLC工程师。请根据以下设备描述生成完整的PLC IO分配表。

严格按照 Markdown 表格格式输出：

## 数字量输入 (DI)
| 地址 | 符号名 | 数据类型 | 说明 | 设备位置 |
|------|--------|----------|------|----------|

## 数字量输出 (DO)
| 地址 | 符号名 | 数据类型 | 说明 | 设备位置 |
|------|--------|----------|------|----------|

## 模拟量输入 (AI)
| 地址 | 符号名 | 数据类型 | 说明 | 量程 | 设备位置 |
|------|--------|----------|------|------|----------|

## 模拟量输出 (AO)
| 地址 | 符号名 | 数据类型 | 说明 | 量程 | 设备位置 |
|------|--------|----------|------|------|----------|

要求：
1. 使用匈牙利命名法 (bStart / qMotor / rTemp)
2. 地址从 I0.0 / Q0.0 / IW64 / QW80 开始合理分配
3. 包含所有安全相关信号（急停、过载、光栅等）
4. 每个信号都要有清晰的设备位置描述

设备描述：
`

export default function IoTableGenerator({ addLog, selectedModel = 'deepseek' }) {
  const [description, setDescription] = useState('')
  const [result, setResult] = useState('')
  // P3 状态机改造：loading: boolean → status: 10 种状态
  const [status, setStatus] = useState('idle')
  const [statusMessage, setStatusMessage] = useState('')
  const [copied, setCopied] = useState(false)
  const { history, save } = useWorkbenchHistory('io-table')
  const loading = status === 'running'
  // F-043 修复：组件卸载时 abort 进行中的 streamChat
  const abortRef = useRef(null)
  useEffect(() => () => abortRef.current?.abort(), [])

  const handleGenerate = async () => {
    if (!description.trim() || loading) return
    setStatus('running')
    setStatusMessage('AI 正在生成 IO 表...')
    setResult('')
    addLog?.('info', `[IO表] 生成中: ${description.slice(0, 50)}...`)
    let fullResult = ''
    // F-043：传 signal 支持卸载时取消；重入时先 abort 前一个请求
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    try {
      await streamChat({
        model_id: selectedModel,
        messages: [{ role: 'user', content: IO_PROMPT + description }],
        temperature: 0.2,
        signal: controller.signal,
        onToken: (token) => { fullResult += token; setResult(prev => prev + token) },
        onDone: (data) => {
          save({ label: description.slice(0, 40), description, result: fullResult })
          if (data?.fallback) {
            addLog?.('warn', `[IO表] 已切换到 ${data.model}`)
            setStatus('model_unavailable')
            setStatusMessage(`主模型不可用，已切换到 ${data.model}`)
          } else {
            setStatus(fullResult ? 'success' : 'no_result')
            setStatusMessage(fullResult ? '生成完成' : '生成完成但无内容')
          }
          addLog?.('info', '[IO表] 完成')
        },
        onError: (err) => {
          setResult(prev => prev || `生成失败: ${err.message}`)
          addLog?.('error', `[IO表] ${err.message}`)
          setStatus('failed')
          setStatusMessage(err.message)
        },
      })
    } catch (err) {
      setResult(`生成失败: ${err.message}`)
      addLog?.('error', `[IO表] ${err.message}`)
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
          <Table2 size={15} className="text-accent" />
          <span className="text-xs text-text-primary font-medium">IO表生成</span>
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
          <label className="text-xs text-text-dim">设备描述</label>
          <textarea
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder={"描述你的设备和控制需求...\n\n示例:\n一条包装生产线，包含：\n- 传送带电机 x2\n- 气缸 x4（推料、夹紧、封口、切断）\n- 光电传感器 x3（入料检测、定位、出料检测）\n- 温度传感器 x1（热封温度）\n- 急停按钮 x2\n- 启动/停止按钮各 x1\n- 三色灯 x1"}
            className="flex-1 bg-ide-bg border border-ide-border rounded p-3 text-xs text-text-primary placeholder-text-dim outline-none focus:border-accent resize-none font-mono"
            spellCheck={false}
          />
          <button onClick={handleGenerate} disabled={loading || !description.trim()}
            className="flex items-center justify-center gap-2 px-4 py-2 bg-accent text-white rounded text-xs font-medium hover:bg-accent-hover disabled:opacity-30 transition-colors">
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {loading ? '生成中...' : '生成 IO 表'}
          </button>
        </div>
      </div>

      {/* Right: Result */}
      <div className="flex-1 flex flex-col">
        <div className="flex items-center gap-2 px-4 py-2 border-b border-ide-border bg-ide-panel">
          <span className="text-xs text-text-primary font-medium">生成结果</span>
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
                            prose-table:border-collapse prose-th:bg-ide-panel prose-th:border prose-th:border-ide-border prose-th:px-3 prose-th:py-1.5
                            prose-td:border prose-td:border-ide-border prose-td:px-3 prose-td:py-1
                            prose-headings:text-text-bright prose-h2:text-sm prose-h2:border-b prose-h2:border-ide-border prose-h2:pb-1">
              <ReactMarkdown>{result}</ReactMarkdown>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-text-dim text-xs">
              {loading ? <><Loader2 size={16} className="animate-spin mr-2" /> 生成中...</> : '在左侧描述设备，点击「生成 IO 表」'}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
