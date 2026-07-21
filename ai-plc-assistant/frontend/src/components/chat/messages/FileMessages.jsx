// 文件 + 导出结果 + 引用来源消息
import {
  Download, File as FileIcon, CheckCircle2, BookOpen,
} from 'lucide-react'
import { parseContent, formatSize, downloadFile } from '../utils'
import { MSG_TYPES } from '../constants'
import PlaceholderMessage from './PlaceholderMessage'

// D-1：文件消息 — 文件名 + 大小 + 下载
export function FileMessage({ content }) {
  const data = parseContent(content)
  const filename = data.filename || data.name || '未命名文件'
  const size = data.size
  const mime = data.mime || data.type
  const url = data.url
  return (
    <div className="flex items-center gap-3 p-3 bg-ide-panel/50 border border-ide-border rounded">
      <FileIcon size={20} className="text-accent shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="text-xs text-text-primary font-mono truncate">{filename}</div>
        <div className="text-2xs text-text-dim flex gap-2">
          {mime && <span>{mime}</span>}
          {size != null && <span>· {formatSize(size)}</span>}
        </div>
      </div>
      {url && (
        <a
          href={url}
          download={filename}
          className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent text-text-secondary transition-colors"
        >
          <Download size={12} /> 下载
        </a>
      )}
    </div>
  )
}

// D-1：导出结果消息 — 成功状态 + 文件信息 + 下载
export function ExportResultMessage({ content }) {
  const data = parseContent(content)
  const filename = data.filename || 'export'
  const format = (data.format || 'unknown').toUpperCase()
  const url = data.url
  const fileContent = data.content
  const mime = data.mime || 'text/plain'
  const handleDownload = () => {
    if (url) {
      window.open(url, '_blank')
    } else if (fileContent) {
      downloadFile(fileContent, filename, mime)
    }
  }
  return (
    <div className="flex items-center gap-3 p-3 bg-status-ok/10 border border-status-ok/30 rounded">
      <CheckCircle2 size={20} className="text-status-ok shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="text-xs text-text-primary">导出成功</div>
        <div className="text-2xs text-text-dim flex gap-2">
          <span className="font-mono">{filename}</span>
          <span>· {format}</span>
        </div>
      </div>
      <button
        type="button"
        onClick={handleDownload}
        className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-status-ok/20 border border-status-ok/40 rounded hover:bg-status-ok/30 text-status-ok transition-colors"
      >
        <Download size={12} /> 下载
      </button>
    </div>
  )
}

// D-1：引用来源消息 — 知识库引用列表
export function CitationMessage({ content }) {
  const data = parseContent(content)
  const sources = data.sources || data.citations || []
  if (!sources.length) return <PlaceholderMessage type={MSG_TYPES.CITATION} content={content} />
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-2xs text-text-dim uppercase tracking-wider">
        <BookOpen size={12} /> 引用来源 ({sources.length})
      </div>
      {sources.map((src, i) => (
        <div key={src.id || src.url || i} className="p-2 bg-ide-panel/50 border border-ide-border rounded">
          <div className="flex items-center gap-2">
            <span className="text-2xs font-mono text-accent shrink-0">#{i + 1}</span>
            <span className="text-xs text-text-primary flex-1 truncate">{src.title || src.name || '未命名来源'}</span>
            {typeof src.score === 'number' && (
              <span className="text-2xs text-text-dim">相关度 {(src.score * 100).toFixed(0)}%</span>
            )}
          </div>
          {src.snippet && (
            <div className="text-2xs text-text-dim mt-1 line-clamp-2">{src.snippet}</div>
          )}
          {src.url && (
            <a
              href={src.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-2xs text-accent mt-1 inline-block hover:underline"
            >
              查看原文 →
            </a>
          )}
        </div>
      ))}
    </div>
  )
}
