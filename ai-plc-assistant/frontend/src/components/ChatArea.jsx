import { useState, useRef, useEffect } from 'react'
import {
  Send, Bot, User, BookOpen, Download, FileCode, FileText as FileXml,
  Table2, ArrowDown, Eye, Code, Square, FileText, Paperclip, AtSign,
  AlertTriangle, Info, CheckCircle2, Loader2, File as FileIcon, Circle,
} from 'lucide-react'
import { exportCode } from '../api'
import ReactMarkdown from 'react-markdown'
import LadderVisualizer from './LadderVisualizer'
import { DataTable, CodeViewer, StatusBadge } from './ui'

/**
 * ChatArea — 工程 AI 工作区（Batch 6 重构）
 *
 * 按主计划 §9：
 * - §9.2 消息类型 13 种：text/markdown/code/variables/io-table/ladder/
 *   task-progress/tool-call/file/warning/error/export-result/citation
 * - §9.3 输入区：当前项目/当前模型/模板/附件/引用工程/输入框/发送/停止生成
 * - §9.4 SSE 状态：当前模型/生成中/停止按钮/已生成内容/错误或回退
 * - §9.5 ASCII-LAD 默认显示（F-026 修复），SVG 不再默认
 */

const MSG_TYPES = {
  TEXT: 'text',
  MARKDOWN: 'markdown',
  CODE: 'code',
  VARIABLES: 'variables',
  IO_TABLE: 'io-table',
  LADDER: 'ladder',
  TASK_PROGRESS: 'task-progress',
  TOOL_CALL: 'tool-call',
  FILE: 'file',
  WARNING: 'warning',
  ERROR: 'error',
  EXPORT_RESULT: 'export-result',
  CITATION: 'citation',
}

function downloadFile(content, filename, mime = 'text/plain') {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// 容错解析 content：对象直接用，字符串尝试 JSON.parse，失败退化到 {text}
function parseContent(content) {
  if (content == null) return {}
  if (typeof content === 'string') {
    try {
      const parsed = JSON.parse(content)
      return typeof parsed === 'object' && parsed !== null ? parsed : { text: content }
    } catch {
      return { text: content }
    }
  }
  return content
}

function formatSize(bytes) {
  if (typeof bytes !== 'number' || bytes < 0) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

async function handleExport(structured, format, title) {
  try {
    const data = await exportCode({
      title: title || 'export',
      variables: structured.variables || [],
      networks: structured.networks || [],
      format,
      block_type: 'FB',
      block_name: title || 'GeneratedBlock',
    })
    downloadFile(data.content, data.filename, data.mime_type)
  } catch (err) {
    alert('导出失败: ' + err.message)
  }
}

function LadderResult({ msg }) {
  const { title, description, structured } = msg
  const { variables, networks } = structured || {}
  // F-026 修复：ASCII-LAD 默认显示（textMode=true），SVG 不再默认
  const [textMode, setTextMode] = useState(true)

  return (
    <div className="space-y-3">
      <div className="text-sm font-medium text-accent">{title}</div>
      {description && <div className="text-2xs text-text-dim">{description}</div>}

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
                  <tr key={v.address || v.name || i} className="border-b border-ide-border last:border-0 text-text-secondary">
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

      {networks?.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-2xs font-medium text-text-secondary uppercase tracking-wider">程序逻辑</div>
            <button
              type="button"
              onClick={() => setTextMode(!textMode)}
              className="flex items-center gap-1 px-2 py-0.5 text-2xs text-text-dim hover:text-accent border border-transparent hover:border-accent/40 rounded transition-colors"
              title={textMode ? '显示图形' : '显示源码'}
            >
              {textMode ? <Eye size={12} /> : <Code size={12} />}
              {textMode ? '图形' : '源码'}
            </button>
          </div>
          {networks.map((n, i) => (
            <div key={n.number || i} className="border border-ide-border rounded overflow-hidden">
              <div className="px-3 py-1.5 bg-ide-panel border-b border-ide-border flex items-center gap-2">
                <span className="text-2xs font-mono text-accent">Network {n.number}</span>
                <span className="text-xs text-text-primary">{n.title}</span>
              </div>
              {n.comment && (
                <div className="px-3 py-1 text-2xs text-text-dim border-b border-ide-border">
                  // {n.comment}
                </div>
              )}
              {n.code && textMode && (
                <pre className="px-3 py-2 text-xs text-text-secondary font-mono leading-relaxed overflow-x-auto bg-ide-panel">
                  {n.code}
                </pre>
              )}
              {n.code && !textMode && (
                <LadderVisualizer networks={[n]} />
              )}
            </div>
          ))}
        </div>
      )}

      {structured && (
        <div className="flex items-center gap-2 pt-2 border-t border-ide-border">
          <span className="text-2xs text-text-dim mr-1">导出:</span>
          <button type="button" onClick={() => handleExport(structured, 'scl', title)}
            className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent transition-colors text-text-secondary">
            <FileCode size={12} /> SCL
          </button>
          <button type="button" onClick={() => handleExport(structured, 'xml', title)}
            className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent transition-colors text-text-secondary">
            <FileXml size={12} /> XML
          </button>
          <button type="button" onClick={() => handleExport(structured, 'csv', title)}
            className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent transition-colors text-text-secondary">
            <Table2 size={12} /> CSV
          </button>
          <button type="button" onClick={() => handleExport(structured, 'hmi', title)}
            className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent transition-colors text-text-secondary">
            <Download size={12} /> HMI
          </button>
        </div>
      )}
    </div>
  )
}

function PlaceholderMessage({ type, content }) {
  const labels = {
    [MSG_TYPES.IO_TABLE]: { icon: Table2, label: 'IO 表', desc: '无结构化数据' },
    [MSG_TYPES.VARIABLES]: { icon: AtSign, label: '变量表', desc: '无结构化数据' },
    [MSG_TYPES.TASK_PROGRESS]: { icon: Loader2, label: '任务进度', desc: '无任务信息' },
    [MSG_TYPES.TOOL_CALL]: { icon: FileCode, label: '工具调用', desc: '无调用详情' },
    [MSG_TYPES.FILE]: { icon: FileIcon, label: '文件', desc: '无文件信息' },
    [MSG_TYPES.EXPORT_RESULT]: { icon: Download, label: '导出结果', desc: '无导出信息' },
    [MSG_TYPES.CITATION]: { icon: BookOpen, label: '引用来源', desc: '无引用' },
  }
  const info = labels[type] || { icon: Info, label: type, desc: '未接入' }
  const Icon = info.icon
  return (
    <div className="flex items-start gap-2 p-3 bg-ide-panel/50 border border-ide-border rounded">
      <Icon size={14} className="text-text-dim shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="text-2xs font-medium text-text-secondary uppercase tracking-wider mb-0.5">{info.label}</div>
        <div className="text-2xs text-text-dim">{info.desc}</div>
        {content && <div className="text-2xs text-text-dim mt-1 truncate">{String(content).slice(0, 200)}</div>}
      </div>
    </div>
  )
}

// F-041：CODE 类型独立分发，用 CodeViewer 渲染（语法高亮 + 复制按钮）
function CodeMessage({ content }) {
  const data = parseContent(content)
  const code = data.code || data.content || data.text || ''
  const language = data.language || 'SCL'
  const title = data.title
  if (!code) return <PlaceholderMessage type={MSG_TYPES.TOOL_CALL} content={content} />
  return <CodeViewer code={code} language={language} title={title} />
}

// D-1：IO 表消息 — 用 DataTable 渲染设备 IO 地址表
function IoTableMessage({ content }) {
  const data = parseContent(content)
  const rows = data.rows || data.io || data.devices || []
  if (!rows.length) return <PlaceholderMessage type={MSG_TYPES.IO_TABLE} content={content} />
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-2xs text-text-dim uppercase tracking-wider">
        <Table2 size={12} /> IO 地址表 ({rows.length})
      </div>
      <DataTable
        columns={[
          { key: 'address', label: '地址', mono: true },
          { key: 'name', label: '符号', mono: true },
          { key: 'type', label: '类型' },
          { key: 'direction', label: '方向' },
          { key: 'comment', label: '注释' },
        ]}
        data={rows}
        rowKey={(row, i) => row.address || row.name || i}
        emptyText="无 IO 数据"
        dense
      />
    </div>
  )
}

// D-1：变量表消息 — 用 DataTable 渲染变量分析结果
function VariablesMessage({ content }) {
  const data = parseContent(content)
  const rows = data.variables || data.rows || data.vars || []
  if (!rows.length) return <PlaceholderMessage type={MSG_TYPES.VARIABLES} content={content} />
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-2xs text-text-dim uppercase tracking-wider">
        <AtSign size={12} /> 变量分析 ({rows.length})
      </div>
      <DataTable
        columns={[
          { key: 'address', label: '地址', mono: true },
          { key: 'name', label: '符号', mono: true },
          { key: 'data_type', label: '类型' },
          { key: 'usage', label: '用法' },
          { key: 'comment', label: '注释' },
        ]}
        data={rows}
        rowKey={(row, i) => row.address || row.name || i}
        emptyText="无变量数据"
        dense
      />
    </div>
  )
}

// D-1：任务进度消息 — 进度条 + 步骤列表
function TaskProgressMessage({ content }) {
  const data = parseContent(content)
  const steps = data.steps || []
  const progress = typeof data.progress === 'number' ? data.progress : 0
  const title = data.title || '任务进行中'
  if (!steps.length && !progress) return <PlaceholderMessage type={MSG_TYPES.TASK_PROGRESS} content={content} />
  return (
    <div className="space-y-2 p-3 bg-ide-panel/50 border border-ide-border rounded">
      <div className="flex items-center gap-2">
        <Loader2 size={14} className="text-accent animate-spin" />
        <span className="text-xs text-text-primary flex-1">{title}</span>
        <span className="text-2xs text-text-dim font-mono">{progress}%</span>
      </div>
      <div className="h-1 bg-ide-border rounded overflow-hidden">
        <div className="h-full bg-accent transition-all" style={{ width: `${progress}%` }} />
      </div>
      {steps.length > 0 && (
        <div className="space-y-1 mt-2">
          {steps.map((step, i) => {
            const status = step.status || 'pending'
            const Icon = status === 'done' ? CheckCircle2
              : status === 'running' ? Loader2
              : status === 'error' ? AlertTriangle
              : Circle
            const color = status === 'done' ? 'text-status-ok'
              : status === 'running' ? 'text-accent'
              : status === 'error' ? 'text-status-error'
              : 'text-text-dim'
            return (
              <div key={step.id || step.name || i} className="flex items-center gap-2 text-2xs">
                <Icon size={11} className={`${color} ${status === 'running' ? 'animate-spin' : ''} shrink-0`} />
                <span className={status === 'done' ? 'text-text-dim line-through' : 'text-text-secondary'}>
                  {step.label || step.name}
                </span>
                {step.detail && <span className="text-text-dim ml-auto truncate">{step.detail}</span>}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// D-1：工具调用消息 — 工具名 + 参数 + 结果
function ToolCallMessage({ content }) {
  const data = parseContent(content)
  const tool = data.tool || data.name || 'unknown'
  const args = data.args || data.arguments || {}
  const result = data.result
  const status = data.status || 'done'
  const tone = status === 'error' ? 'danger' : status === 'running' ? 'info' : 'success'
  return (
    <div className="border border-ide-border rounded overflow-hidden">
      <div className="px-3 py-1.5 bg-ide-panel border-b border-ide-border flex items-center gap-2">
        <FileCode size={12} className="text-accent" />
        <span className="text-2xs font-mono text-accent flex-1">{tool}</span>
        <StatusBadge tone={tone}>{status}</StatusBadge>
      </div>
      {Object.keys(args).length > 0 && (
        <div className="px-3 py-2 border-b border-ide-border">
          <div className="text-2xs text-text-dim mb-1 uppercase tracking-wider">参数</div>
          <pre className="text-2xs text-text-secondary font-mono whitespace-pre-wrap overflow-x-auto">{JSON.stringify(args, null, 2)}</pre>
        </div>
      )}
      {result != null && (
        <div className="px-3 py-2">
          <div className="text-2xs text-text-dim mb-1 uppercase tracking-wider">结果</div>
          <pre className="text-2xs text-text-secondary font-mono whitespace-pre-wrap overflow-x-auto">
            {typeof result === 'string' ? result : JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

// D-1：文件消息 — 文件名 + 大小 + 下载
function FileMessage({ content }) {
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
function ExportResultMessage({ content }) {
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
function CitationMessage({ content }) {
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

function WarningMessage({ content }) {
  return (
    <div className="flex items-start gap-2 p-3 bg-status-warn/10 border border-status-warn/30 rounded">
      <AlertTriangle size={14} className="text-status-warn shrink-0 mt-0.5" />
      <div className="flex-1 text-xs text-status-warn whitespace-pre-wrap">{content}</div>
    </div>
  )
}

function ErrorMessage({ content }) {
  return (
    <div className="flex items-start gap-2 p-3 bg-status-error/10 border border-status-error/30 rounded">
      <AlertTriangle size={14} className="text-status-error shrink-0 mt-0.5" />
      <div className="flex-1 text-xs text-status-error whitespace-pre-wrap">{content}</div>
    </div>
  )
}

function MessageBlock({ msg }) {
  const isUser = msg.role === 'user'
  const msgType = msg.type || MSG_TYPES.TEXT

  return (
    <div className={`border-b border-ide-border ${isUser ? 'bg-ide-bg' : 'bg-ide-sidebar/50'}`}>
      <div className="max-w-4xl mx-auto px-4 py-3">
        <div className="flex items-center gap-2 mb-2">
          {isUser ? (
            <User size={14} className="text-text-dim" />
          ) : (
            <Bot size={14} className="text-accent" />
          )}
          <span className="text-2xs font-medium text-text-dim uppercase tracking-wider">
            {isUser ? '输入' : 'AI 助手'}
          </span>
          {msg.fallback && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-2xs bg-status-warn/15 text-status-warn border border-status-warn/30">
              已切换至 {msg.model || '备用模型'}
            </span>
          )}
          {msg.model && !msg.fallback && !isUser && (
            <span className="text-2xs text-text-dim">{msg.model}</span>
          )}
          {msg.stopped && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-2xs bg-ide-panel text-text-dim border border-ide-border">
              已停止
            </span>
          )}
          {msg.streaming && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-2xs text-accent animate-pulse">
              生成中...
            </span>
          )}
          {msg.rag_sources?.length > 0 && (
            <span className="flex items-center gap-1 text-2xs text-status-info ml-auto">
              <BookOpen size={11} /> 引用 {msg.rag_sources.length} 个文档
            </span>
          )}
        </div>

        {isUser ? (
          <div className="text-sm text-text-primary whitespace-pre-wrap">{msg.content}</div>
        ) : msgType === MSG_TYPES.LADDER ? (
          <LadderResult msg={msg} />
        ) : msgType === MSG_TYPES.WARNING ? (
          <WarningMessage content={msg.content} />
        ) : msgType === MSG_TYPES.ERROR ? (
          <ErrorMessage content={msg.content} />
        ) : msgType === MSG_TYPES.CODE ? (
          <CodeMessage content={msg.content} />
        ) : msgType === MSG_TYPES.IO_TABLE ? (
          <IoTableMessage content={msg.content} />
        ) : msgType === MSG_TYPES.VARIABLES ? (
          <VariablesMessage content={msg.content} />
        ) : msgType === MSG_TYPES.TASK_PROGRESS ? (
          <TaskProgressMessage content={msg.content} />
        ) : msgType === MSG_TYPES.TOOL_CALL ? (
          <ToolCallMessage content={msg.content} />
        ) : msgType === MSG_TYPES.FILE ? (
          <FileMessage content={msg.content} />
        ) : msgType === MSG_TYPES.EXPORT_RESULT ? (
          <ExportResultMessage content={msg.content} />
        ) : msgType === MSG_TYPES.CITATION ? (
          <CitationMessage content={msg.content} />
        ) : (
          <div className="prose prose-invert max-w-none prose-sm text-text-primary
                          prose-code:bg-ide-panel prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-accent
                          prose-pre:bg-ide-panel prose-pre:border prose-pre:border-ide-border prose-pre:rounded
                          prose-headings:text-text-bright prose-a:text-accent">
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  )
}

function ChatInput({
  input, setInput, onSubmit, onKeyDown, sending, onStop,
  currentProject, selectedModel, onOpenTemplates, onAddAttachment,
}) {
  // P4 附件上传：hidden file input + ref 触发
  const fileRef = useRef(null)
  const handleAttachmentClick = () => {
    fileRef.current?.click()
  }
  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file && onAddAttachment) {
      onAddAttachment(file)
    }
    // 清空 input value 允许重复选同一文件
    e.target.value = ''
  }
  return (
    <div className="border-t border-ide-border bg-ide-sidebar">
      {/* §9.4 SSE 状态栏：当前项目 + 当前模型 + 生成状态 */}
      <div className="flex items-center gap-3 px-4 py-1.5 border-b border-ide-border text-2xs">
        <span className="text-text-dim">
          项目: <span className="text-text-secondary font-mono">{currentProject?.name || '未选择'}</span>
        </span>
        <span className="text-text-dim">·</span>
        <span className="text-text-dim">
          模型: <span className="text-text-secondary font-mono">{selectedModel || '-'}</span>
        </span>
        {sending && (
          <span className="flex items-center gap-1 text-accent ml-auto">
            <Loader2 size={11} className="animate-spin" />
            生成中
          </span>
        )}
      </div>

      {/* §9.3 输入区 */}
      <form onSubmit={onSubmit} className="max-w-4xl mx-auto p-3 flex gap-2 items-end">
        {/* 二级菜单：模板 / 附件 / 引用工程 */}
        <button
          type="button"
          onClick={onOpenTemplates}
          title="提示词模板"
          className="px-2 py-2 text-text-dim hover:text-accent border border-ide-border rounded transition-colors"
        >
          <FileText size={14} />
        </button>
        <button
          type="button"
          onClick={handleAttachmentClick}
          title="上传附件到知识库"
          className="px-2 py-2 text-text-dim hover:text-accent border border-ide-border rounded transition-colors"
        >
          <Paperclip size={14} />
        </button>
        {/* P4：hidden file input，由附件按钮触发 */}
        <input
          ref={fileRef}
          type="file"
          className="hidden"
          onChange={handleFileChange}
          accept=".pdf,.docx,.txt,.md,.json,.csv,.xlsx,.html"
        />
        <button
          type="button"
          title={`引用工程: ${currentProject?.name || '未选择'}`}
          className="px-2 py-2 text-text-dim hover:text-accent border border-ide-border rounded transition-colors"
        >
          <AtSign size={14} />
        </button>

        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={sending}
          placeholder={sending ? '处理中...' : '输入指令或 PLC 编程需求... (Enter 发送, Shift+Enter 换行)'}
          rows={1}
          className="flex-1 bg-ide-input border border-ide-border rounded px-3 py-2 text-sm text-text-primary placeholder-text-dim outline-none focus:border-accent transition-colors disabled:opacity-50 resize-none min-h-[38px] max-h-32"
        />

        {sending ? (
          <button
            type="button"
            onClick={onStop}
            className="px-4 py-2 bg-status-error text-white rounded text-xs font-medium hover:bg-status-error/90 transition-colors flex items-center gap-1.5"
          >
            <Square size={13} /> 停止
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim()}
            className="px-4 py-2 bg-accent text-white rounded text-xs font-medium hover:bg-accent-hover disabled:opacity-30 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
          >
            <Send size={13} /> 发送
          </button>
        )}
      </form>
    </div>
  )
}

export default function ChatArea({
  messages,
  onSend,
  onStop,
  initialInput = '',
  sending = false,
  currentProject,
  selectedModel,
  onOpenTemplates,
  onAddAttachment,
}) {
  const [input, setInput] = useState(initialInput)
  const [showScrollBtn, setShowScrollBtn] = useState(false)
  const endRef = useRef(null)
  const scrollRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (initialInput) {
      setInput(initialInput)
      inputRef.current?.focus()
    }
  }, [initialInput])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleScroll = () => {
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100
    setShowScrollBtn(!atBottom)
  }

  const scrollToBottom = () => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || sending) return
    onSend(text)
    setInput('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <main className="flex-1 flex flex-col overflow-hidden bg-ide-bg">
      <div className="flex-1 overflow-hidden relative">
        <div ref={scrollRef} onScroll={handleScroll} className="h-full overflow-y-auto">
          {messages.length === 0 ? (
            <div className="h-full flex items-center justify-center text-text-dim text-xs">
              <div className="text-center">
                <Bot size={32} className="mx-auto mb-2 opacity-50" />
                <div>开始新的 AI 对话</div>
                <div className="text-2xs mt-1">输入需求或选择模板</div>
              </div>
            </div>
          ) : (
            messages.map((msg, i) => (
              <MessageBlock key={msg.id || `${i}-${msg.role}`} msg={msg} />
            ))
          )}
          <div ref={endRef} />
        </div>
        {showScrollBtn && (
          <button
            type="button"
            onClick={scrollToBottom}
            className="absolute bottom-4 right-6 w-8 h-8 bg-ide-panel border border-ide-border rounded-full flex items-center justify-center text-text-dim hover:text-accent hover:border-accent/40 shadow-lg transition-colors"
          >
            <ArrowDown size={16} />
          </button>
        )}
      </div>

      <ChatInput
        input={input}
        setInput={setInput}
        onSubmit={handleSubmit}
        onKeyDown={handleKeyDown}
        sending={sending}
        onStop={onStop}
        currentProject={currentProject}
        selectedModel={selectedModel}
        onOpenTemplates={onOpenTemplates}
        onAddAttachment={onAddAttachment}
      />
    </main>
  )
}
