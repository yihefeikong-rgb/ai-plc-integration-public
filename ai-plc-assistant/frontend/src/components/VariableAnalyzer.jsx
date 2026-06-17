import { useState } from 'react'
import { Play, Loader2, Variable, Copy, Check, Clock } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { streamChat } from '../api'
import useWorkbenchHistory from '../hooks/useWorkbenchHistory'

const VARIABLE_PROMPT = `你是一名西门子PLC工程师。请分析下面的PLC代码，提取并分析所有变量。

请按以下结构回答：

## 变量汇总
| 地址 | 符号名 | 数据类型 | 用途 | 所属段 |
|------|--------|----------|------|--------|

## 输入信号 (I)
列出所有数字量/模拟量输入，说明每个信号的来源设备和作用。

## 输出信号 (Q)
列出所有数字量/模拟量输出，说明每个信号驱动的设备。

## 中间变量 (M/DB)
列出所有内部标志位、定时器、计数器，说明用途。

## 地址分配建议
检查地址是否有冲突或不规范之处，给出优化建议。

## 缺失变量
根据程序逻辑，指出可能缺少的变量（如急停、过载、故障标志等）。

代码如下：
`

export default function VariableAnalyzer({ addLog }) {
  const [code, setCode] = useState('')
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)
  const { history, save } = useWorkbenchHistory('variable-analyzer')

  const handleAnalyze = async () => {
    if (!code.trim() || loading) return
    setLoading(true)
    setResult('')
    addLog?.('info', `[变量分析] ${code.length} 字符`)
    let fullResult = ''

    try {
      await streamChat({
        model_id: 'deepseek',
        messages: [{ role: 'user', content: VARIABLE_PROMPT + code }],
        temperature: 0.2,
        onToken: (token) => { fullResult += token; setResult(prev => prev + token) },
        onDone: () => { save({ label: code.slice(0, 40), code, result: fullResult }); addLog?.('info', '[变量分析] 完成') },
        onError: (err) => {
          setResult(prev => prev || `分析失败: ${err.message}`)
          addLog?.('error', `[变量分析] ${err.message}`)
        },
      })
    } catch (err) {
      setResult(`分析失败: ${err.message}`)
      addLog?.('error', `[变量分析] ${err.message}`)
    }
    setLoading(false)
  }

  return (
    <div className="flex-1 flex overflow-hidden bg-ide-bg">
      {/* Left: Code input */}
      <div className="flex-1 flex flex-col border-r border-ide-border">
        <div className="flex items-center gap-2 px-4 py-2 border-b border-ide-border bg-ide-panel">
          <Variable size={15} className="text-accent" />
          <span className="text-xs text-text-primary font-medium">变量分析</span>
          <div className="flex-1" />
          {history.length > 0 && (
            <select onChange={e => { const h = history.find(x => x.id === e.target.value); if (h) { setCode(h.code); setResult(h.result) } }} value=""
              style={{ color: '#CCC', backgroundColor: '#3C3C3C' }}
              className="border border-ide-border rounded px-2 py-1 text-2xs outline-none">
              <option value="">历史 ({history.length})</option>
              {history.map(h => <option key={h.id} value={h.id}>{h.time} — {h.label}...</option>)}
            </select>
          )}
          <button onClick={handleAnalyze} disabled={loading || !code.trim()}
            className="flex items-center gap-1.5 px-3 py-1 bg-accent text-white rounded text-xs font-medium hover:bg-accent-hover disabled:opacity-30 transition-colors">
            {loading ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
            {loading ? '分析中...' : '分析变量'}
          </button>
        </div>
        <textarea value={code} onChange={e => setCode(e.target.value)}
          placeholder={"粘贴 PLC 代码，AI 将提取并分析所有变量...\n\n支持 SCL / LAD / STL / FBD 代码"}
          className="flex-1 bg-ide-bg text-text-primary font-mono text-xs leading-relaxed p-4 outline-none resize-none placeholder-text-dim"
          spellCheck={false} />
        <div className="flex items-center px-4 py-1 border-t border-ide-border bg-ide-panel text-2xs text-text-dim">
          <span>{code.length} 字符</span>
          <span className="mx-2">|</span>
          <span>{code.split('\n').length} 行</span>
        </div>
      </div>

      {/* Right: Result */}
      <div className="flex-1 flex flex-col">
        <div className="flex items-center gap-2 px-4 py-2 border-b border-ide-border bg-ide-panel">
          <span className="text-xs text-text-primary font-medium">分析结果</span>
          <div className="flex-1" />
          {result && (
            <button onClick={() => { navigator.clipboard.writeText(result); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
              className="flex items-center gap-1 px-2 py-0.5 text-2xs text-text-dim hover:text-text-primary border border-ide-border rounded">
              {copied ? <Check size={11} /> : <Copy size={11} />}
              {copied ? '已复制' : '复制'}
            </button>
          )}
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {result ? (
            <div className="prose prose-invert max-w-none prose-sm text-text-primary
                            [&_table]:block [&_table]:overflow-x-auto [&_table]:w-full
                            prose-table:border-collapse prose-th:bg-ide-panel prose-th:border prose-th:border-ide-border prose-th:px-2 prose-th:py-1.5 prose-th:whitespace-nowrap prose-th:text-2xs
                            prose-td:border prose-td:border-ide-border prose-td:px-2 prose-td:py-1 prose-td:text-xs
                            prose-headings:text-text-bright prose-h2:text-sm prose-h2:border-b prose-h2:border-ide-border prose-h2:pb-1">
              <ReactMarkdown>{result}</ReactMarkdown>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-text-dim text-xs">
              {loading ? <><Loader2 size={16} className="animate-spin mr-2" /> 分析中...</> : '在左侧粘贴 PLC 代码，点击「分析变量」'}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
