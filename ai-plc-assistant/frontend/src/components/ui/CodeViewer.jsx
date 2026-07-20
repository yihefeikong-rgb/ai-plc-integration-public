import React, { useState } from 'react'
import { Copy, Check } from 'lucide-react'

/**
 * CodeViewer — 代码查看器（带复制按钮 + 等宽字体）
 *
 * 用法：
 *   <CodeViewer code={sclCode} language="SCL" />
 *   <CodeViewer code={asciiLad} language="ASCII-LAD" title="Network 1" />
 */
export default function CodeViewer({
  code,
  language,
  title,
  className = '',
  maxHeight = '400px',
  showCopy = true,
}) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  if (!code) {
    return <div className="text-text-dim text-xs p-3">无代码内容</div>
  }

  return (
    <div className={`border border-ide-border rounded overflow-hidden bg-ide-panel ${className}`}>
      {(title || language || showCopy) && (
        <div className="flex items-center gap-2 px-3 py-1.5 border-b border-ide-border bg-ide-panel">
          {title && <span className="text-xs text-text-primary flex-1">{title}</span>}
          {language && (
            <span className="text-2xs text-text-dim font-mono uppercase">{language}</span>
          )}
          {showCopy && (
            <button
              type="button"
              onClick={handleCopy}
              className="flex items-center gap-1 px-2 py-0.5 text-2xs text-text-dim hover:text-text-primary border border-ide-border rounded"
              aria-label="复制代码"
            >
              {copied ? <Check size={11} /> : <Copy size={11} />}
              {copied ? '已复制' : '复制'}
            </button>
          )}
        </div>
      )}
      <pre
        className="px-3 py-2 text-xs text-text-secondary font-mono leading-relaxed overflow-auto"
        style={{ maxHeight }}
      >
        {code}
      </pre>
    </div>
  )
}
