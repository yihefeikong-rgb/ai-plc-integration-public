import { useState, useRef, useEffect } from 'react'
import { Circle, Cpu } from 'lucide-react'

function MenuDropdown({ label, items, onAction }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`px-3 py-1 text-xs rounded transition-colors ${
          open ? 'bg-ide-active text-text-primary' : 'text-text-secondary hover:text-text-primary hover:bg-ide-hover'
        }`}
      >
        {label}
      </button>

      {open && (
        <div className="absolute left-0 top-full mt-0.5 bg-ide-sidebar border border-ide-border rounded shadow-xl z-50 min-w-[200px] py-1">
          {items.map((item, i) =>
            item.separator ? (
              <div key={i} className="my-1 border-t border-ide-border" />
            ) : (
              <button
                key={i}
                disabled={item.disabled}
                onClick={() => { setOpen(false); onAction?.(item.action) }}
                className={`w-full text-left px-4 py-1.5 text-xs flex items-center justify-between ${
                  item.disabled
                    ? 'text-text-dim cursor-not-allowed'
                    : 'text-text-secondary hover:bg-accent/15 hover:text-text-primary'
                }`}
              >
                <span>{item.label}</span>
                {item.shortcut && <span className="text-text-dim text-2xs ml-6">{item.shortcut}</span>}
              </button>
            )
          )}
        </div>
      )}
    </div>
  )
}

const menuConfig = [
  {
    label: '项目',
    items: [
      { label: '新建项目', action: 'project:new', shortcut: 'Ctrl+N' },
      { label: '导入工程', action: 'project:import' },
      { separator: true },
      { label: '项目设置', action: 'project:settings' },
    ],
  },
  {
    label: '编辑',
    items: [
      { label: '撤销', action: 'edit:undo', shortcut: 'Ctrl+Z', disabled: true },
      { label: '重做', action: 'edit:redo', shortcut: 'Ctrl+Y', disabled: true },
      { separator: true },
      { label: '剪切', action: 'edit:cut', shortcut: 'Ctrl+X', disabled: true },
      { label: '复制', action: 'edit:copy', shortcut: 'Ctrl+C', disabled: true },
      { label: '粘贴', action: 'edit:paste', shortcut: 'Ctrl+V', disabled: true },
    ],
  },
  {
    label: '工具',
    items: [
      { label: '梯形图生成', action: 'tool:ladder' },
      { label: '程序解析', action: 'tool:parse' },
      { label: 'IO表生成', action: 'tool:io-table' },
      { label: '变量分析', action: 'tool:variables' },
      { label: '故障诊断', action: 'tool:diagnose' },
      { separator: true },
      { label: '工程搜索', action: 'tool:search' },
      { label: '索引当前工程', action: 'tool:index' },
    ],
  },
  {
    label: 'AI',
    items: [
      { label: '新建对话', action: 'ai:new-chat' },
      { separator: true },
      { label: '模板库', action: 'ai:templates' },
      { label: '知识库管理', action: 'ai:knowledge' },
    ],
  },
  {
    label: '视图',
    items: [
      { label: '切换侧栏', action: 'view:sidebar', shortcut: 'Ctrl+B' },
      { label: '切换右面板', action: 'view:context', shortcut: 'Ctrl+J' },
      { label: '切换底部面板', action: 'view:bottom', shortcut: 'Ctrl+`' },
    ],
  },
  {
    label: '帮助',
    items: [
      { label: '编排管理教程', action: 'help:orchestrator-tutorial' },
      { label: '关于 AI PLC Assistant', action: 'help:about' },
      { label: 'API 文档', action: 'help:api-docs' },
    ],
  },
]

export default function Toolbar({ models, selectedModel, onSelectModel, onMenuAction }) {
  const [showModelMenu, setShowModelMenu] = useState(false)
  const modelRef = useRef(null)

  const currentModel = models.find(m => m.id === selectedModel)

  useEffect(() => {
    const handler = (e) => { if (modelRef.current && !modelRef.current.contains(e.target)) setShowModelMenu(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <header className="h-12 flex items-center bg-ide-panel border-b border-ide-border select-none shrink-0 px-3 gap-0.5">
      {/* Logo */}
      <div className="flex items-center gap-2 mr-3 pr-3 border-r border-ide-border">
        <Cpu size={18} className="text-accent" />
        <span className="text-text-primary text-xs font-semibold tracking-wide">AI PLC</span>
      </div>

      {/* Menus */}
      {menuConfig.map(menu => (
        <MenuDropdown key={menu.label} label={menu.label} items={menu.items} onAction={onMenuAction} />
      ))}

      <div className="flex-1" />

      {/* Model selector */}
      <div ref={modelRef} className="relative">
        <button
          onClick={() => setShowModelMenu(!showModelMenu)}
          className="flex items-center gap-2 px-3 py-1 text-xs text-text-secondary hover:text-text-primary hover:bg-ide-hover rounded transition-colors"
        >
          <Circle size={7} fill={currentModel?.enabled ? '#4EC9B0' : '#6A6A6A'}
            className={currentModel?.enabled ? 'text-status-ok' : 'text-text-dim'} />
          <span>{currentModel?.name || selectedModel}</span>
        </button>

        {showModelMenu && (
          <div className="absolute right-0 top-full mt-0.5 bg-ide-sidebar border border-ide-border rounded shadow-xl z-50 min-w-[180px] py-1">
            {models.map(m => (
              <button key={m.id} disabled={!m.enabled}
                onClick={() => { onSelectModel(m.id); setShowModelMenu(false) }}
                className={`w-full text-left px-4 py-1.5 text-xs flex items-center gap-2 ${
                  m.id === selectedModel ? 'bg-accent/15 text-accent'
                    : m.enabled ? 'text-text-secondary hover:bg-ide-hover' : 'text-text-dim cursor-not-allowed'
                }`}>
                <Circle size={6} fill={m.enabled ? '#4EC9B0' : '#6A6A6A'}
                  className={m.enabled ? 'text-status-ok' : 'text-text-dim'} />
                {m.name}
              </button>
            ))}
          </div>
        )}
      </div>
    </header>
  )
}
