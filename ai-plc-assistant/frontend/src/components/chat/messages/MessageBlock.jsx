// 消息分发器 — 根据 msg.type 渲染对应组件
import { User, Bot, BookOpen } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { MSG_TYPES } from '../constants'
import LadderResult from './LadderResult'
import CodeMessage from './CodeMessage'
import PlaceholderMessage from './PlaceholderMessage'
import { IoTableMessage, VariablesMessage } from './TableMessages'
import { TaskProgressMessage, ToolCallMessage } from './ProgressMessages'
import { FileMessage, ExportResultMessage, CitationMessage } from './FileMessages'
import { WarningMessage, ErrorMessage } from './StatusMessages'

export default function MessageBlock({ msg }) {
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
