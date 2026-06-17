import { useState, useEffect } from 'react'
import {
  Code2, FileSearch, Search, FolderInput,
  Clock, ArrowRight, FolderOpen, Plus, MessageSquare,
} from 'lucide-react'
import { listProjects, listConversations, getTemplateCategories } from '../api'

const quickActions = [
  { id: 'ladder', icon: Code2, label: '生成梯形图', desc: '自然语言生成PLC程序' },
  { id: 'parse', icon: FileSearch, label: '解析PLC程序', desc: '上传程序自动分析' },
  { id: 'search', icon: Search, label: '搜索知识库', desc: '检索案例和文档' },
  { id: 'import', icon: FolderInput, label: '导入工程', desc: '导入TIA Portal项目' },
]

function timeAgo(ts) {
  if (!ts) return ''
  const diff = (Date.now() / 1000) - ts
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  if (diff < 604800) return `${Math.floor(diff / 86400)}天前`
  return new Date(ts * 1000).toLocaleDateString()
}

export default function Dashboard({ onOpenTab, onCreateProject }) {
  const [projects, setProjects] = useState([])
  const [conversations, setConversations] = useState([])
  const [templates, setTemplates] = useState([])

  useEffect(() => {
    listProjects(5).then(d => setProjects(d.projects || [])).catch(() => {})
    listConversations(5).then(d => setConversations(d.conversations || [])).catch(() => {})
    getTemplateCategories().then(d => {
      const cats = (d.categories || []).map(c => c.name)
      setTemplates(cats)
    }).catch(() => setTemplates(['交通灯控制', '电机正反转', 'PID温度调节', 'Modbus通信']))
  }, [])

  return (
    <div className="flex-1 overflow-y-auto p-8 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-lg font-semibold text-text-bright mb-1">欢迎回来</h1>
        <p className="text-xs text-text-dim">AI PLC Assistant v1.0 — 工业自动化编程工作台</p>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-4 gap-3 mb-8">
        {quickActions.map((a) => (
          <button
            key={a.id}
            onClick={() => onOpenTab?.(a.id)}
            className="bg-ide-sidebar border border-ide-border rounded p-4 text-left hover:border-accent/40 hover:bg-ide-hover transition-colors"
          >
            <a.icon size={20} className="text-accent mb-3" />
            <div className="text-sm text-text-primary font-medium mb-1">{a.label}</div>
            <div className="text-2xs text-text-dim">{a.desc}</div>
          </button>
        ))}
      </div>

      {/* Recent Projects */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">最近项目</h2>
          <button onClick={onCreateProject} className="text-2xs text-accent flex items-center gap-1 hover:underline">
            <Plus size={11} /> 新建项目
          </button>
        </div>
        <div className="bg-ide-sidebar border border-ide-border rounded divide-y divide-ide-border">
          {projects.length === 0 ? (
            <div className="px-4 py-6 text-center text-text-dim text-xs">
              暂无项目，点击上方"新建项目"开始
            </div>
          ) : (
            projects.map((p) => (
              <button
                key={p.id}
                onClick={() => onOpenTab?.('project', p)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-ide-hover transition-colors text-left group"
              >
                <FolderOpen size={16} className="text-accent shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-text-primary">{p.name}</div>
                  <div className="text-2xs text-text-dim truncate">{p.plc_type} / {p.tia_version} / {p.language}</div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-2xs text-text-dim flex items-center gap-1">
                    <Clock size={11} /> {timeAgo(p.last_opened_at)}
                  </span>
                  <ArrowRight size={14} className="text-text-dim opacity-0 group-hover:opacity-100" />
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Recent Conversations */}
      {conversations.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">最近对话</h2>
          <div className="bg-ide-sidebar border border-ide-border rounded divide-y divide-ide-border">
            {conversations.map((c) => (
              <button
                key={c.id}
                onClick={() => onOpenTab?.('chat')}
                className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-ide-hover transition-colors text-left"
              >
                <MessageSquare size={14} className="text-text-dim shrink-0" />
                <span className="text-xs text-text-secondary flex-1 truncate">{c.title}</span>
                <span className="text-2xs text-text-dim">{timeAgo(c.updated_at)}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Templates */}
      <div>
        <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">常用模板</h2>
        <div className="flex flex-wrap gap-2">
          {templates.map((t) => (
            <button
              key={t}
              onClick={() => onOpenTab?.('templates')}
              className="px-3 py-1.5 bg-ide-sidebar border border-ide-border rounded text-xs text-text-secondary hover:text-accent hover:border-accent/30 transition-colors"
            >
              {t}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
