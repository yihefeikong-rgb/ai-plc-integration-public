// InspectorPanel — 右侧检查器面板（按 activeTab 变化，8 种内容）
//
// 按主计划 §7.5：welcome / chat / ladder / io-table / parse / diagnose / orchestrator / settings
// D-3 填充：每种 Inspector 基于 currentProject + messages + selectedModel 显示结构化内容
import { Cpu, Inbox } from 'lucide-react'
import EmptyState from '../../components/ui/EmptyState'
import WelcomeInspector from './WelcomeInspector'
import ChatInspector from './ChatInspector'
import LadderInspector from './LadderInspector'
import IoTableInspector from './IoTableInspector'
import ParseInspector from './ParseInspector'
import DiagnoseInspector from './DiagnoseInspector'
import OrchestratorInspector from './OrchestratorInspector'
import VariablesInspector from './VariablesInspector'
import SettingsInspector from './SettingsInspector'

const INSPECTOR_MAP = {
  welcome: { component: WelcomeInspector, isCustom: true },
  chat: { component: ChatInspector, isCustom: true },
  ladder: { component: LadderInspector, isCustom: true },
  'io-table': { component: IoTableInspector, isCustom: true },
  parse: { component: ParseInspector, isCustom: true },
  diagnose: { component: DiagnoseInspector, isCustom: true },
  orchestrator: { component: OrchestratorInspector, isCustom: true },
  variables: { component: VariablesInspector, isCustom: true },
  settings: { component: SettingsInspector, isCustom: true },
  robot: { icon: Cpu },
}

export default function InspectorPanel({ addLog, currentProject, activeTab, messages = [], selectedModel, conversations = [] }) {
  const inspector = INSPECTOR_MAP[activeTab] || INSPECTOR_MAP.welcome

  return (
    <aside className="w-full bg-ide-sidebar border-l border-ide-border flex flex-col shrink-0 overflow-hidden h-full">
      <div className="flex-1 overflow-y-auto">
        {inspector.isCustom ? (
          <inspector.component
            addLog={addLog}
            currentProject={currentProject}
            messages={messages}
            selectedModel={selectedModel}
            conversations={conversations}
          />
        ) : (
          <div className="p-3">
            <div className="flex items-center gap-2 px-2 py-2 text-2xs font-semibold uppercase tracking-wider text-text-dim border-b border-ide-border">
              {inspector.icon && <inspector.icon size={13} />}
              <span>Inspector</span>
            </div>
            <div className="p-3">
              <EmptyState icon={Inbox} description="未接入" />
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}
