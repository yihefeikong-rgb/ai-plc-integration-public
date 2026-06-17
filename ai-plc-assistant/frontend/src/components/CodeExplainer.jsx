import { useState } from 'react'
import { Play, Loader2, Code2, Copy, Check } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

const LANGUAGES = [
  { id: 'scl', label: 'SCL' },
  { id: 'lad', label: 'LAD (梯形图)' },
  { id: 'stl', label: 'STL / AWL' },
  { id: 'fbd', label: 'FBD' },
  { id: 'auto', label: '自动识别' },
]

const EXPLAIN_PROMPT = (lang) => `请解析下面的PLC代码（语言：${lang}）。

请按以下结构回答：

## 功能概述
简要说明这段代码实现了什么功能。

## 变量说明
列出关键变量的名称、类型和作用。

## 逻辑流程
逐步说明程序的执行逻辑。

## 安全分析
检查是否有：互锁逻辑、急停处理、故障保护。

## 优化建议
如果有可以改进的地方，给出建议。

代码如下：
`

const API_BASE = 'http://127.0.0.1:8005/api'

export default function CodeExplainer({ addLog }) {
  const [code, setCode] = useState('')
  const [language, setLanguage] = useState('auto')
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleExplain = async () => {
    if (!code.trim() || loading) return
    setLoading(true)
    setResult('')
    addLog?.('info', `[代码解析] 语言: ${language}, ${code.length} 字符`)

    try {
      const langLabel = LANGUAGES.find(l => l.id === language)?.label || language
      const prompt = EXPLAIN_PROMPT(langLabel) + code

      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_id: 'deepseek',
          messages: [{ role: 'user', content: prompt }],
          temperature: 0.2,
        }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }

      const data = await res.json()
      setResult(data.content)
      if (data.fallback) {
        addLog?.('warn', `[代码解析] 主模型不可用，已切换到 ${data.model}`)
      }
      addLog?.('info', `[代码解析] 完成 (${data.content.length} 字符)`)
    } catch (err) {
      setResult(`解析失败: ${err.message}\n\n请检查后端是否已启动，API Key 是否配置正确。`)
      addLog?.('error', `[代码解析] ${err.message}`)
    }
    setLoading(false)
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(result)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="flex-1 flex overflow-hidden bg-ide-bg">
      {/* Left: Code input */}
      <div className="flex-1 flex flex-col border-r border-ide-border">
        {/* Toolbar */}
        <div className="flex items-center gap-3 px-4 py-2 border-b border-ide-border bg-ide-panel">
          <Code2 size={15} className="text-accent" />
          <span className="text-xs text-text-primary font-medium">代码解析</span>
          <div className="flex-1" />
          <select
            value={language}
            onChange={e => setLanguage(e.target.value)}
            style={{ color: '#CCC', backgroundColor: '#3C3C3C' }}
            className="border border-ide-border rounded px-2 py-1 text-xs outline-none focus:border-accent"
          >
            {LANGUAGES.map(l => (
              <option key={l.id} value={l.id} style={{ color: '#CCC', backgroundColor: '#3C3C3C' }}>{l.label}</option>
            ))}
          </select>
          <button
            onClick={handleExplain}
            disabled={loading || !code.trim()}
            className="flex items-center gap-1.5 px-3 py-1 bg-accent text-white rounded text-xs font-medium hover:bg-accent-hover disabled:opacity-30 transition-colors"
          >
            {loading ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
            {loading ? '解析中...' : '解析代码'}
          </button>
        </div>

        {/* Code textarea */}
        <textarea
          value={code}
          onChange={e => setCode(e.target.value)}
          placeholder={`粘贴 PLC 代码到这里...\n\n示例:\nFUNCTION_BLOCK "MotorControl"\nVAR_INPUT\n    bStart : Bool;\n    bStop : Bool;\nEND_VAR\nVAR_OUTPUT\n    qMotor : Bool;\nEND_VAR\nBEGIN\n    qMotor := bStart AND NOT bStop;\nEND_FUNCTION_BLOCK`}
          className="flex-1 bg-ide-bg text-text-primary font-mono text-xs leading-relaxed p-4 outline-none resize-none placeholder-text-dim"
          spellCheck={false}
        />

        {/* Status bar */}
        <div className="flex items-center px-4 py-1 border-t border-ide-border bg-ide-panel text-2xs text-text-dim">
          <span>{code.length} 字符</span>
          <span className="mx-2">|</span>
          <span>{code.split('\n').length} 行</span>
          <span className="mx-2">|</span>
          <span>{LANGUAGES.find(l => l.id === language)?.label}</span>
        </div>
      </div>

      {/* Right: Result */}
      <div className="flex-1 flex flex-col">
        <div className="flex items-center gap-2 px-4 py-2 border-b border-ide-border bg-ide-panel">
          <span className="text-xs text-text-primary font-medium">解析结果</span>
          <div className="flex-1" />
          {result && (
            <button onClick={handleCopy}
              className="flex items-center gap-1 px-2 py-0.5 text-2xs text-text-dim hover:text-text-primary border border-ide-border rounded">
              {copied ? <Check size={11} /> : <Copy size={11} />}
              {copied ? '已复制' : '复制'}
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {result ? (
            <div className="prose prose-invert max-w-none prose-sm text-text-primary
                            prose-code:bg-ide-panel prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-accent
                            prose-pre:bg-ide-panel prose-pre:border prose-pre:border-ide-border prose-pre:rounded
                            prose-headings:text-text-bright prose-h2:text-sm prose-h2:border-b prose-h2:border-ide-border prose-h2:pb-1">
              <ReactMarkdown>{result}</ReactMarkdown>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-text-dim text-xs">
              {loading ? (
                <div className="flex items-center gap-2">
                  <Loader2 size={16} className="animate-spin" />
                  AI 正在解析代码...
                </div>
              ) : (
                '在左侧粘贴 PLC 代码，点击「解析代码」查看结果'
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
