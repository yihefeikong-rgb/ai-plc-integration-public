import { useState } from 'react'
import { X } from 'lucide-react'
import Toolbar from './components/Toolbar'
import Sidebar from './components/Sidebar'
import Dashboard from './components/Dashboard'
import ChatArea from './components/ChatArea'
import ContextPanel from './components/ContextPanel'
import LogPanel from './components/LogPanel'
import PromptTemplateModal from './components/PromptTemplateModal'
import CodeTemplateModal from './components/CodeTemplateModal'
import LadderTemplateModal from './components/LadderTemplateModal'
import SettingsPanel from './components/SettingsPanel'
import CodeExplainer from './components/CodeExplainer'
import IoTableGenerator from './components/IoTableGenerator'
import FaultDiagnosis from './components/FaultDiagnosis'
import LadderGenerator from './components/LadderGenerator'
import VariableAnalyzer from './components/VariableAnalyzer'
import CreateProjectDialog from './components/CreateProjectDialog'
import ErrorBoundary from './components/ErrorBoundary'
import useLogs from './hooks/useLogs'
import useTabs, { TAB_LABELS } from './hooks/useTabs'
import useModels from './hooks/useModels'
import useProjects from './hooks/useProjects'
import useConversation from './hooks/useConversation'

export default function App() {
  const { logs, addLog } = useLogs()
  const { tabs, activeTab, setActiveTab, openTab, closeTab } = useTabs()
  const { models, selectedModel, setSelectedModel } = useModels()
  const { currentProject, setCurrentProject, handleCreateProject, handleImportProject, importRef } = useProjects({ addLog })
  const { convId, conversations, messages, sending, pendingInput, setPendingInput, handleNewConversation, handleSwitchConversation, handleDeleteConversation, handleSend } = useConversation({ addLog, openTab, selectedModel, currentProject })

  const [showTemplates, setShowTemplates] = useState(false)
  const [showCodeTemplate, setShowCodeTemplate] = useState(false)
  const [showLadderTemplate, setShowLadderTemplate] = useState(false)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showSidebar, setShowSidebar] = useState(true)
  const [showContext, setShowContext] = useState(true)
  const [showBottom, setShowBottom] = useState(true)

  const openCreateDialog = () => setShowCreateDialog(true)

  // 统一入口: 处理特殊 tab (templates / project) + 普通 tab
  const handleOpenTab = (id, data) => {
    if (id === 'templates') { setShowTemplates(true); return }
    if (id === 'project' && data) {
      setCurrentProject(data)
      addLog('info', `[项目] ${data.name}`)
      return
    }
    openTab(id)
  }

  const handleTemplateSelect = (content) => {
    setPendingInput(content)
    openTab('chat')
  }

  const handleMenuAction = (action) => {
    switch (action) {
      case 'project:new': openCreateDialog(); break
      case 'project:import': importRef.current?.click(); break
      case 'project:settings': openTab('settings'); break
      case 'tool:ladder': openTab('ladder'); break
      case 'tool:parse': openTab('parse'); break
      case 'tool:io-table': openTab('io-table'); break
      case 'tool:variables': openTab('variables'); break
      case 'tool:diagnose': openTab('diagnose'); break
      case 'tool:search': openTab('chat'); break
      case 'tool:index': addLog('info', '[工具] 请在右侧面板使用工程搜索'); break
      case 'ai:new-chat': handleNewConversation(); break
      case 'ai:templates': setShowTemplates(true); break
      case 'ai:knowledge': openTab('chat'); break
      case 'view:sidebar': setShowSidebar(v => !v); break
      case 'view:context': setShowContext(v => !v); break
      case 'view:bottom': setShowBottom(v => !v); break
      case 'help:about': addLog('info', 'AI PLC Assistant v1.0 — 工业自动化编程工作台'); break
      case 'help:api-docs': window.open('http://127.0.0.1:8005/docs', '_blank'); break
    }
  }

  // Tab → 组件映射（已打开的 Tab 保持挂载，切走不丢状态）
  const workspaces = {
    welcome: <Dashboard onOpenTab={handleOpenTab} onCreateProject={openCreateDialog} />,
    chat: <ChatArea messages={messages} onSend={handleSend} initialInput={pendingInput} sending={sending} />,
    parse: <CodeExplainer addLog={addLog} />,
    'io-table': <IoTableGenerator addLog={addLog} />,
    diagnose: <FaultDiagnosis addLog={addLog} />,
    ladder: <LadderGenerator addLog={addLog} />,
    variables: <VariableAnalyzer addLog={addLog} />,
    settings: <SettingsPanel addLog={addLog} />,
  }

  return (
    <ErrorBoundary>
    <div className="h-full flex flex-col">
      <Toolbar models={models} selectedModel={selectedModel} onSelectModel={setSelectedModel} onMenuAction={handleMenuAction} />

      <div className="flex items-center h-8 bg-ide-panel border-b border-ide-border overflow-x-auto">
        {tabs.map(tab => (
          <div key={tab.id}
            className={`flex items-center gap-1 px-3 h-full border-r border-ide-border cursor-pointer text-xs shrink-0 ${
              activeTab === tab.id ? 'bg-ide-bg text-text-primary border-t-2 border-t-accent' : 'text-text-dim hover:text-text-secondary hover:bg-ide-hover'
            }`}
            onClick={() => setActiveTab(tab.id)}>
            <span>{TAB_LABELS[tab.id] || tab.id}</span>
            {tab.closable && (
              <button onClick={e => { e.stopPropagation(); closeTab(tab.id) }} className="ml-1 hover:text-text-primary">
                <X size={12} />
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="flex-1 flex overflow-hidden">
        {showSidebar && (
          <Sidebar onOpenTab={handleOpenTab} activeTab={activeTab} addLog={addLog}
            onCreateProject={openCreateDialog} currentProject={currentProject}
            conversations={conversations} currentConvId={convId}
            onSwitchConversation={handleSwitchConversation} onDeleteConversation={handleDeleteConversation}
            onNewConversation={handleNewConversation}
            onOpenCodeTemplates={() => setShowCodeTemplate(true)}
            onOpenLadderTemplates={() => setShowLadderTemplate(true)} />
        )}
        {tabs.map(tab => workspaces[tab.id] && (
          <div key={tab.id} style={{ display: activeTab === tab.id ? 'flex' : 'none' }} className="flex-1 overflow-hidden">
            {workspaces[tab.id]}
          </div>
        ))}
        {showContext && <ContextPanel addLog={addLog} currentProject={currentProject} />}
      </div>

      {showBottom && <LogPanel logs={logs} />}

      <input ref={importRef} type="file" accept=".ap18,.ap19,.ap17,.zip" onChange={handleImportProject} className="hidden" />

      {showTemplates && (
        <PromptTemplateModal onClose={() => setShowTemplates(false)} onSelect={handleTemplateSelect} />
      )}

      {showCodeTemplate && (
        <CodeTemplateModal onClose={() => setShowCodeTemplate(false)} />
      )}

      {showLadderTemplate && (
        <LadderTemplateModal
          onClose={() => setShowLadderTemplate(false)}
          onUseTemplate={(prompt) => { setPendingInput(prompt); openTab('chat') }}
        />
      )}

      {showCreateDialog && (
        <CreateProjectDialog
          onSubmit={(data) => { handleCreateProject(data); setShowCreateDialog(false) }}
          onCancel={() => setShowCreateDialog(false)}
        />
      )}
    </div>
    </ErrorBoundary>
  )
}
