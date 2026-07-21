// 占位消息 — 当消息没有结构化数据时的 fallback
import { Table2, AtSign, Loader2, FileCode, File as FileIcon, Download, BookOpen, Info } from 'lucide-react'
import { MSG_TYPES } from '../constants'

export default function PlaceholderMessage({ type, content }) {
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
