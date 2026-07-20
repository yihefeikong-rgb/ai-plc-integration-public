import { useState, useRef, useEffect, useMemo } from 'react'
import {
  FolderOpen, ChevronRight, ChevronDown, Plus, Upload,
  BookOpen, FileText, LayoutTemplate, Code as CodeIcon,
  Zap, AlertTriangle, Table2, Variable,
  Settings, Trash2, MessageSquare, PlusCircle, Cpu,
  Home, Bot, ScrollText, FileSearch,
} from 'lucide-react'
import { listProjects, uploadDocument, listDocuments, deleteDocument, importProject } from '../api'

/**
 * PrimarySidebar — 主侧栏（4 分组：项目/工作区/资源/系统）
 *
 * 按主计划 §7.4 重组：
 * - 项目：当前工程 / 最近工程 / 新建工程 / 导入工程
 * - 工作区：总览 / AI 助手 / 梯形图 / IO 表 / 程序解析 / 变量分析 / 故障诊断
 * - 资源：对话 / LAD 模板 / SCL 模板 / 提示词模板 / 知识库
 * - 系统：编排管理 / 机器人 / 日志 / 设置
 */

function Section({ title, icon: Icon, defaultOpen = false, count, children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div>
      <button
        type="button"
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
      type="button"
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

function DocGroup({ label, icon: Icon, docs, prefixRange, onDelete }) {
  const [open, setOpen] = useState(false)
  const [min, max] = prefixRange || [0, 99]
  const groupDocs = useMemo(
    () =>
      docs.filter((d) => {
        const m = (d.filename || '').match(/^(\d+)/)
        const n = m ? parseInt(m[1], 10) : 99
        return n >= min && n <= max
      }),
    [docs, min, max],
  )
  if (groupDocs.length === 0) return null
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-1.5 pl-6 pr-3 py-1 text-2xs font-medium text-text-dim hover:text-text-secondary"
      >
        {open ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
        <Icon size={12} />
        <span>{label}</span>
        <span className="ml-auto text-text-dim font-normal">{groupDocs.length}篇</span>
      </button>
      {open &&
        groupDocs.map((doc) => (
          <div
            key={doc.document_id}
            className="group flex items-center gap-1 pl-9 pr-3 py-0.5 text-xs text-text-dim hover:bg-ide-hover"
          >
            <FileText size={12} className="shrink-0" />
            <span className="truncate flex-1">{doc.filename.replace(/\.txt$/, '')}</span>
            <span className="text-2xs">{doc.chunk_count}</span>
            <button
              type="button"
              onClick={() => onDelete(doc.document_id, doc.filename)}
              className="opacity-0 group-hover:opacity-100 text-text-dim hover:text-status-error ml-1"
              aria-label="删除文档"
            >
              <Trash2 size={11} />
            </button>
          </div>
        ))}
    </div>
  )
}

// 工作区分组 7 项（与 TAB_LABELS 对齐）
const WORKSPACE_ITEMS = [
  { id: 'welcome', label: '总览', icon: Home },
  { id: 'chat', label: 'AI 助手', icon: Bot },
  { id: 'ladder', label: '梯形图', icon: Zap },
  { id: 'io-table', label: 'IO 表', icon: Table2 },
  { id: 'parse', label: '程序解析', icon: FileSearch },
  { id: 'variables', label: '变量分析', icon: Variable },
  { id: 'diagnose', label: '故障诊断', icon: AlertTriangle },
]

// 系统分组 4 项
const SYSTEM_ITEMS = [
  { id: 'orchestrator', label: '编排管理', icon: Cpu },
  { id: 'robot', label: '机器人', icon: Cpu },
  { id: 'settings', label: '设置', icon: Settings },
]

export default function PrimarySidebar({
  onOpenTab,
  activeTab,
  addLog,
  onCreateProject,
  currentProject,
  conversations = [],
  currentConvId,
  onSwitchConversation,
  onDeleteConversation,
  onNewConversation,
  onOpenCodeTemplates,
  onOpenLadderTemplates,
  onShowBottom,
  onActivateBottomTab,
}) {
  const fileRef = useRef(null)
  const importRef = useRef(null)
  const [projects, setProjects] = useState([])
  const [docs, setDocs] = useState([])
  const [uploading, setUploading] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(null)

  useEffect(() => {
    listProjects(20).then((d) => setProjects(d.projects || [])).catch(() => {})
  }, [currentProject])

  useEffect(() => {
    listDocuments().then((d) => setDocs(d.documents || [])).catch(() => {})
  }, [])

  const refreshDocs = async () => {
    try {
      const d = await listDocuments()
      setDocs(d.documents || [])
    } catch {}
  }

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const result = await uploadDocument(file)
      addLog?.('info', `[知识库] 导入: ${result.filename} (${result.chunk_count}块)`)
      refreshDocs()
    } catch (err) {
      addLog?.('error', `[知识库] 导入失败: ${err.message}`)
    }
    setUploading(false)
    e.target.value = ''
  }

  const handleDelete = async (docId, filename) => {
    try {
      await deleteDocument(docId)
      addLog?.('info', `[知识库] 已删除: ${filename}`)
      refreshDocs()
    } catch (err) {
      addLog?.('error', `[知识库] 删除失败: ${err.message}`)
    }
  }

  const handleImportProject = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    addLog?.('info', `[导入] ${file.name} (${(file.size / 1024 / 1024).toFixed(1)}MB)`)
    try {
      const d = await importProject(file)
      onOpenTab?.('project', d.project)
      addLog?.('info', `[导入] 完成: ${d.project.name}`)
    } catch (err) {
      addLog?.('error', `[导入] 失败: ${err.message}`)
    }
    e.target.value = ''
  }

  const handleShowLogs = () => {
    onShowBottom?.(true)
    onActivateBottomTab?.('log')
  }

  return (
    <aside className="w-full bg-ide-sidebar border-r border-ide-border flex flex-col shrink-0 overflow-hidden h-full">
      <div className="flex-1 overflow-y-auto">
        {/* ===== 项目分组 ===== */}
        <Section title="项目" icon={FolderOpen} defaultOpen={true} count={projects.length}>
          {currentProject && (
            <SidebarItem
              icon={FolderOpen}
              label={currentProject.name}
              active
              onClick={() => onOpenTab?.('project', currentProject)}
              indent
            />
          )}
          {projects
            .filter((p) => !currentProject || p.id !== currentProject.id)
            .slice(0, 5)
            .map((p) => (
              <SidebarItem
                key={p.id}
                icon={FolderOpen}
                label={p.name}
                onClick={() => onOpenTab?.('project', p)}
                indent
                dimLabel
              />
            ))}
          <button
            type="button"
            onClick={onCreateProject}
            className="w-full flex items-center gap-2 pl-5 px-3 py-1 text-xs text-accent hover:bg-ide-hover"
          >
            <Plus size={13} /> 新建工程
          </button>
          <button
            type="button"
            onClick={() => importRef.current?.click()}
            className="w-full flex items-center gap-2 pl-5 px-3 py-1 text-xs text-accent hover:bg-ide-hover"
          >
            <Upload size={13} /> 导入工程
          </button>
          <input
            ref={importRef}
            type="file"
            accept=".ap18,.ap19,.ap17,.zip"
            onChange={handleImportProject}
            className="hidden"
          />
        </Section>

        {/* ===== 工作区分组 ===== */}
        <Section title="工作区" icon={Zap} defaultOpen={true}>
          {WORKSPACE_ITEMS.map((t) => (
            <SidebarItem
              key={t.id}
              icon={t.icon}
              label={t.label}
              active={activeTab === t.id}
              onClick={() => onOpenTab?.(t.id)}
              indent
            />
          ))}
        </Section>

        {/* ===== 资源分组 ===== */}
        <Section title="资源" icon={BookOpen} defaultOpen={false} count={conversations.length + docs.length}>
          {/* 对话 */}
          <div className="pt-1">
            <div className="text-2xs text-text-dim px-7 py-0.5">对话</div>
            {conversations.slice(0, 10).map((c) => (
              <div
                key={c.id}
                className={`group flex items-center gap-2 pl-9 pr-3 py-1 text-xs cursor-pointer transition-colors ${
                  currentConvId === c.id
                    ? 'bg-accent/10 text-accent'
                    : 'text-text-dim hover:text-text-secondary hover:bg-ide-hover'
                }`}
                onClick={() => onSwitchConversation?.(c.id)}
              >
                <MessageSquare size={14} className="shrink-0" />
                <span className="truncate flex-1">{c.title}</span>
                {deleteConfirm === c.id ? (
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); onDeleteConversation?.(c.id); setDeleteConfirm(null) }}
                      className="text-status-error hover:text-status-error/80 text-2xs font-medium"
                    >
                      确认
                    </button>
                    <span className="text-text-dim text-2xs">/</span>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); setDeleteConfirm(null) }}
                      className="text-text-dim hover:text-text-primary text-2xs"
                    >
                      取消
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); setDeleteConfirm(c.id) }}
                    className="opacity-0 group-hover:opacity-100 text-text-dim hover:text-status-error shrink-0"
                    aria-label="删除对话"
                  >
                    <Trash2 size={11} />
                  </button>
                )}
              </div>
            ))}
            <button
              type="button"
              onClick={onNewConversation}
              className="w-full flex items-center gap-2 pl-9 px-3 py-1 text-xs text-accent hover:bg-ide-hover"
            >
              <PlusCircle size={13} /> 新建对话
            </button>
          </div>

          {/* 模板 */}
          <div className="pt-1">
            <div className="text-2xs text-text-dim px-7 py-0.5">模板</div>
            <SidebarItem icon={LayoutTemplate} label="提示词模板" onClick={() => onOpenTab?.('templates')} indent />
            <SidebarItem icon={CodeIcon} label="SCL 代码模板" onClick={() => onOpenCodeTemplates?.()} indent />
            <SidebarItem icon={CodeIcon} label="梯形图模板" onClick={() => onOpenLadderTemplates?.()} indent />
          </div>

          {/* 知识库 */}
          <div className="pt-1">
            <div className="text-2xs text-text-dim px-7 py-0.5">知识库</div>
            <input ref={fileRef} type="file" accept=".pdf,.docx,.txt" onChange={handleUpload} className="hidden" />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="w-full flex items-center gap-2 pl-9 px-3 py-1 text-xs text-accent hover:bg-ide-hover disabled:opacity-50"
            >
              <Upload size={13} /> {uploading ? '上传中...' : '导入文档'}
            </button>
            <DocGroup label="基础参考" icon={BookOpen} docs={docs} prefixRange={[1, 3]} onDelete={handleDelete} />
            <DocGroup label="进阶参考" icon={FileText} docs={docs} prefixRange={[4, 10]} onDelete={handleDelete} />
            <DocGroup label="行业模板" icon={LayoutTemplate} docs={docs} prefixRange={[11, 99]} onDelete={handleDelete} />
          </div>
        </Section>

        {/* ===== 系统分组 ===== */}
        <Section title="系统" icon={Settings} defaultOpen={true}>
          {SYSTEM_ITEMS.map((t) => (
            <SidebarItem
              key={t.id}
              icon={t.icon}
              label={t.label}
              active={activeTab === t.id}
              onClick={() => onOpenTab?.(t.id)}
              indent
            />
          ))}
          <SidebarItem icon={ScrollText} label="日志" onClick={handleShowLogs} indent />
        </Section>
      </div>
    </aside>
  )
}
