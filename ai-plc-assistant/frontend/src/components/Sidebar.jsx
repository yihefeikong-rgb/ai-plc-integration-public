import { useState, useRef, useEffect, useMemo } from 'react'
import {
  FolderOpen, ChevronRight, ChevronDown, Plus, Upload,
  BookOpen, FileText, LayoutTemplate, Code as CodeIcon,
  Zap, Code2, AlertTriangle, Table2, Variable,
  Settings, Trash2, MessageSquare, PlusCircle,
} from 'lucide-react'
import { listProjects, uploadDocument, listDocuments, deleteDocument, listConversations } from '../api'

function Section({ title, icon: Icon, defaultOpen = false, count, children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-1.5 px-3 py-1.5 text-2xs font-semibold uppercase tracking-wider text-text-dim hover:text-text-secondary"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <Icon size={13} />
        <span>{title}</span>
        {count !== undefined && <span className="ml-auto text-text-dim font-normal">{count}</span>}
      </button>
      {open && <div className="pb-1">{children}</div>}
    </div>
  )
}

function SidebarItem({ icon: Icon, label, count, onClick, active, indent = false, dimLabel = false }) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-2 px-3 py-1 text-xs transition-colors ${indent ? 'pl-7' : 'pl-5'} ${
        active ? 'bg-accent/10 text-accent' : 'text-text-secondary hover:text-text-primary hover:bg-ide-hover'
      }`}
    >
      <Icon size={14} className="shrink-0" />
      <span className={`truncate flex-1 text-left ${dimLabel ? 'text-text-dim' : ''}`}>{label}</span>
      {count !== undefined && <span className="text-text-dim text-2xs">{count}</span>}
    </button>
  )
}

/* 可折叠的知识库文档分组 */
function DocGroup({ label, icon: Icon, docs, prefixRange, onDelete }) {
  const [open, setOpen] = useState(false)
  const [min, max] = prefixRange || [0, 99]
  const groupDocs = useMemo(() =>
    docs.filter(d => {
      const m = (d.filename || '').match(/^(\d+)/)
      const n = m ? parseInt(m[1]) : 99
      return n >= min && n <= max
    }),
    [docs, min, max]
  )
  if (groupDocs.length === 0) return null
  return (
    <div>
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-1.5 pl-6 pr-3 py-1 text-2xs font-medium text-text-dim hover:text-text-secondary">
        {open ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
        <Icon size={12} />
        <span>{label}</span>
        <span className="ml-auto text-text-dim font-normal">{groupDocs.length}篇</span>
      </button>
      {open && groupDocs.map(doc => (
        <div key={doc.document_id}
          className="group flex items-center gap-1 pl-9 pr-3 py-0.5 text-xs text-text-dim hover:bg-ide-hover">
          <FileText size={12} className="shrink-0" />
          <span className="truncate flex-1">{doc.filename.replace(/\.txt$/,'')}</span>
          <span className="text-2xs">{doc.chunk_count}</span>
          <button onClick={() => onDelete(doc.document_id, doc.filename)}
            className="opacity-0 group-hover:opacity-100 text-text-dim hover:text-status-error ml-1">
            <Trash2 size={11} />
          </button>
        </div>
      ))}
    </div>
  )
}

const aiTools = [
  { id: 'ladder', label: '梯形图生成', icon: Code2 },
  { id: 'parse', label: '程序解析', icon: FileText },
  { id: 'diagnose', label: '故障诊断', icon: AlertTriangle },
  { id: 'io-table', label: 'IO表生成', icon: Table2 },
  { id: 'variables', label: '变量分析', icon: Variable },
]

export default function Sidebar({
  onOpenTab, activeTab, addLog, onCreateProject, currentProject,
  conversations = [], currentConvId, onSwitchConversation, onDeleteConversation, onNewConversation,
  onOpenCodeTemplates,
  onOpenLadderTemplates,
}) {
  const fileRef = useRef(null)
  const [projects, setProjects] = useState([])
  const [docs, setDocs] = useState([])
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    listProjects(20).then(d => setProjects(d.projects || [])).catch(() => {})
  }, [currentProject]) // 创建/切换项目后刷新列表

  useEffect(() => {
    listDocuments().then(d => setDocs(d.documents || [])).catch(() => {})
  }, [])

  const refreshDocs = async () => {
    try { const d = await listDocuments(); setDocs(d.documents || []) } catch {}
  }

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const result = await uploadDocument(file)
      addLog?.('info', `[知识库] 导入: ${result.filename} (${result.chunk_count}块)`)
      refreshDocs()
    } catch (err) { addLog?.('error', `[知识库] 导入失败: ${err.message}`) }
    setUploading(false)
    e.target.value = ''
  }

  const handleDelete = async (docId, filename) => {
    try {
      await deleteDocument(docId)
      addLog?.('info', `[知识库] 已删除: ${filename}`)
      refreshDocs()
    } catch (err) { addLog?.('error', `[知识库] 删除失败: ${err.message}`) }
  }

  return (
    <aside className="w-[260px] bg-ide-sidebar border-r border-ide-border flex flex-col shrink-0 overflow-hidden">
      <div className="flex-1 overflow-y-auto">
        {/* 工程 */}
        <Section title="工程" icon={FolderOpen} defaultOpen={true} count={projects.length}>
          {projects.map((p) => (
            <SidebarItem key={p.id} icon={FolderOpen} label={p.name}
              active={currentProject?.id === p.id} onClick={() => onOpenTab?.('project', p)} indent />
          ))}
          <button onClick={onCreateProject}
            className="w-full flex items-center gap-2 pl-5 px-3 py-1 text-xs text-accent hover:bg-ide-hover">
            <Plus size={13} /> 新建项目
          </button>
        </Section>

        {/* 对话 */}
        <Section title="对话" icon={MessageSquare} defaultOpen={true} count={conversations.length}>
          {conversations.map((c) => (
            <div key={c.id}
              className={`group flex items-center gap-2 pl-7 pr-3 py-1 text-xs cursor-pointer transition-colors ${
                currentConvId === c.id ? 'bg-accent/10 text-accent' : 'text-text-dim hover:text-text-secondary hover:bg-ide-hover'
              }`}
              onClick={() => onSwitchConversation?.(c.id)}>
              <MessageSquare size={14} className="shrink-0" />
              <span className="truncate flex-1">{c.title}</span>
              <button onClick={(e) => { e.stopPropagation(); onDeleteConversation?.(c.id) }}
                className="opacity-0 group-hover:opacity-100 text-text-dim hover:text-status-error shrink-0">
                <Trash2 size={11} />
              </button>
            </div>
          ))}
          <button onClick={onNewConversation}
            className="w-full flex items-center gap-2 pl-5 px-3 py-1 text-xs text-accent hover:bg-ide-hover">
            <PlusCircle size={13} /> 新建对话
          </button>
        </Section>

        {/* 知识库 */}
        <Section title="知识库" icon={BookOpen} defaultOpen={false} count={docs.length}>
          <SidebarItem icon={LayoutTemplate} label="提示词模板" onClick={() => onOpenTab?.('templates')} indent />
          <SidebarItem icon={CodeIcon} label="SCL代码模板" onClick={() => onOpenCodeTemplates?.()} indent />
          <SidebarItem icon={CodeIcon} label="梯形图模板" onClick={() => onOpenLadderTemplates?.()} indent />
          <input ref={fileRef} type="file" accept=".pdf,.docx,.txt" onChange={handleUpload} className="hidden" />
          <button onClick={() => fileRef.current?.click()} disabled={uploading}
            className="w-full flex items-center gap-2 pl-5 px-3 py-1 text-xs text-accent hover:bg-ide-hover disabled:opacity-50">
            <Upload size={13} /> {uploading ? '上传中...' : '导入文档'}
          </button>

          {/* 分组文档列表 */}
          <DocGroup label="基础参考" icon={BookOpen} docs={docs} prefixRange={[1, 3]} indent="pl-7" onDelete={handleDelete} />
          <DocGroup label="进阶参考" icon={FileText} docs={docs} prefixRange={[4, 10]} indent="pl-7" onDelete={handleDelete} />
          <DocGroup label="行业模板" icon={LayoutTemplate} docs={docs} prefixRange={[11, 99]} indent="pl-7" onDelete={handleDelete} />
        </Section>

        {/* AI工具 */}
        <Section title="AI 工具" icon={Zap} defaultOpen={true}>
          {aiTools.map((t) => (
            <SidebarItem key={t.id} icon={t.icon} label={t.label}
              active={activeTab === t.id} onClick={() => onOpenTab?.(t.id)} indent />
          ))}
        </Section>

        {/* 设置 */}
        <Section title="设置" icon={Settings}>
          <SidebarItem icon={Settings} label="模型配置"
            onClick={() => onOpenTab?.('settings')} indent />
        </Section>
      </div>
    </aside>
  )
}
