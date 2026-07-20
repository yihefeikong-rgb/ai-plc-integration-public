import { X } from 'lucide-react'
import { TAB_LABELS } from '../hooks/useTabs'

/**
 * WorkspaceTabs — 工作区标签栏
 *
 * 从 App.jsx 107-122 行迁移。横向滚动，closable tab 显示关闭按钮。
 */
export default function WorkspaceTabs({ tabs, activeTab, setActiveTab, closeTab }) {
  return (
    <div className="flex items-center h-8 bg-ide-panel border-b border-ide-border overflow-x-auto">
      {tabs.map((tab) => (
        <div
          key={tab.id}
          className={`flex items-center gap-1 px-3 h-full border-r border-ide-border cursor-pointer text-xs shrink-0 ${
            activeTab === tab.id
              ? 'bg-ide-bg text-text-primary border-t-2 border-t-accent'
              : 'text-text-dim hover:text-text-secondary hover:bg-ide-hover'
          }`}
          onClick={() => setActiveTab(tab.id)}
        >
          <span>{TAB_LABELS[tab.id] || tab.id}</span>
          {tab.closable && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); closeTab(tab.id) }}
              className="ml-1 hover:text-text-primary"
              aria-label="关闭标签"
            >
              <X size={12} />
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
