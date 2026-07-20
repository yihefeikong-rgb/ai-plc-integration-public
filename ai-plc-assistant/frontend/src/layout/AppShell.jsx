import { useState, useEffect, useCallback, useMemo } from 'react'
import TopBar from './TopBar'
import WorkspaceTabs from './WorkspaceTabs'
import PrimarySidebar from './PrimarySidebar'
import MainWorkspace from './MainWorkspace'
import InspectorPanel from './InspectorPanel'
import BottomPanel from './BottomPanel'
import PromptTemplateModal from '../components/PromptTemplateModal'
import CodeTemplateModal from '../components/CodeTemplateModal'
import LadderTemplateModal from '../components/LadderTemplateModal'
import CreateProjectDialog from '../components/CreateProjectDialog'
import ErrorBoundary from '../components/ErrorBoundary'
import useLogs from '../hooks/useLogs'
import useTabs from '../hooks/useTabs'
import useModels from '../hooks/useModels'
import useProjects from '../hooks/useProjects'
import useConversation from '../hooks/useConversation'
import { API_DOCS_URL } from '../api'
import { LayoutContext, MODALS } from './AppContext'

/**
 * AppShell — 应用外壳顶层组件
 *
 * 组合：TopBar + WorkspaceTabs + (PrimarySidebar | MainWorkspace | InspectorPanel) + BottomPanel + Modals
 *
 * 持有：
 * - 6 个 hooks（useLogs/useTabs/useModels/useProjects/useConversation）
 * - 3 个面板可见性（showSidebar/showContext/showBottom，localStorage 持久化）
 * - 5 个 Modal 状态
 * - 1 个 Tutorial 状态
 * - LayoutContext.Provider（openTab/addLog/activeTab/registerModal）
 */

const PANEL_STORAGE_KEYS = {
  sidebar: 'panel.sidebar',
  context: 'panel.context',
  bottom: 'panel.bottom',
}

function usePersistentState(key, defaultValue) {
  const [value, setValue] = useState(() => {
    if (typeof localStorage === 'undefined') return defaultValue
    try {
      const saved = localStorage.getItem(key)
      if (saved !== null) return saved === 'true'
    } catch {}
    return defaultValue
  })
  useEffect(() => {
    try { localStorage.setItem(key, String(value)) } catch {}
  }, [key, value])
  return [value, setValue]
}

export default function AppShell() {
  const { logs, addLog } = useLogs()
  const { tabs, activeTab, setActiveTab, openTab, closeTab } = useTabs()
  const { models, selectedModel, setSelectedModel } = useModels()
  const { currentProject, setCurrentProject, handleCreateProject, handleImportProject, importRef } = useProjects({ addLog })
  const {
    convId, conversations, messages, sending, pendingInput, setPendingInput,
    handleNewConversation, handleSwitchConversation, handleDeleteConversation, handleSend, handleStop,
  } = useConversation({ addLog, openTab, selectedModel, currentProject })

  const [showSidebar, setShowSidebar] = usePersistentState(PANEL_STORAGE_KEYS.sidebar, true)
  const [showContext, setShowContext] = usePersistentState(PANEL_STORAGE_KEYS.context, true)
  const [showBottom, setShowBottom] = usePersistentState(PANEL_STORAGE_KEYS.bottom, true)

  const [showTemplates, setShowTemplates] = useState(false)
  const [showCodeTemplate, setShowCodeTemplate] = useState(false)
  const [showLadderTemplate, setShowLadderTemplate] = useState(false)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showAbout, setShowAbout] = useState(false)
  const [showOrchTutorial, setShowOrchTutorial] = useState(false)
  const [bottomTab, setBottomTab] = useState('log')
  // BottomPanel 折叠状态独立于 showBottom 挂载状态，避免折叠=卸载导致 Tab 栏消失
  const [bottomCollapsed, setBottomCollapsed] = useState(false)

  const openCreateDialog = () => setShowCreateDialog(true)

  // 菜单/快捷操作触发文件选择器（importRef 稳定，可空依赖）
  const handleImportProjectClick = useCallback(() => {
    importRef.current?.click()
  }, [])

  // 统一入口：处理特殊 tab (templates / project) + 普通 tab
  const handleOpenTab = useCallback((id, data) => {
    if (id === 'templates') {
      setShowTemplates(true)
      return
    }
    if (id === 'project' && data) {
      setCurrentProject(data)
      addLog('info', `[项目] ${data.name}`)
      return
    }
    openTab(id)
  }, [openTab, setCurrentProject, addLog])

  const handleTemplateSelect = useCallback((content) => {
    setPendingInput(content)
    openTab('chat')
  }, [setPendingInput, openTab])

  const handleMenuAction = useCallback((action) => {
    switch (action) {
      case 'project:new': openCreateDialog(); break
      case 'project:import': importRef.current?.click(); break
      case 'project:settings': openTab('settings'); break
      case 'tool:search': openTab('chat'); break
      case 'tool:index': addLog('info', '[工具] 请在右侧面板使用工程搜索'); break
      case 'ai:new-chat': handleNewConversation(); break
      case 'ai:templates': setShowTemplates(true); break
      case 'ai:knowledge': setShowSidebar(true); break
      case 'view:sidebar': setShowSidebar((v) => !v); break
      case 'view:context': setShowContext((v) => !v); break
      case 'view:bottom': setShowBottom((v) => !v); break
      case 'help:about': setShowAbout(true); break
      case 'help:api-docs': window.open(API_DOCS_URL, '_blank'); break
      case 'help:orchestrator-tutorial':
        openTab('orchestrator')
        setShowOrchTutorial(true)
        break
    }
  }, [openTab, addLog, handleNewConversation, importRef, setShowSidebar, setShowContext, setShowBottom])

  // 键盘快捷键：Ctrl+B/J/` — setter 引用稳定（React 18 useState dispatch），仅 mount 时绑定一次
  useEffect(() => {
    const handler = (e) => {
      if (e.ctrlKey && e.key === 'b') { e.preventDefault(); setShowSidebar((v) => !v) }
      else if (e.ctrlKey && e.key === 'j') { e.preventDefault(); setShowContext((v) => !v) }
      else if (e.ctrlKey && e.key === '`') { e.preventDefault(); setShowBottom((v) => !v) }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // registerModal 稳定引用：setter 来自 useState，React 18 保证稳定
  const registerModal = useCallback((name) => {
    if (name === MODALS.PROMPT_TEMPLATE) setShowTemplates(true)
    else if (name === MODALS.CODE_TEMPLATE) setShowCodeTemplate(true)
    else if (name === MODALS.LADDER_TEMPLATE) setShowLadderTemplate(true)
    else if (name === MODALS.CREATE_PROJECT) setShowCreateDialog(true)
    else if (name === MODALS.ABOUT) setShowAbout(true)
  }, [])

  // layoutContextValue memo 化：避免每次渲染新建对象导致消费组件强制 re-render
  const layoutContextValue = useMemo(() => ({
    openTab: handleOpenTab,
    addLog,
    activeTab,
    registerModal,
  }), [handleOpenTab, addLog, activeTab, registerModal])

  return (
    <ErrorBoundary>
      <LayoutContext.Provider value={layoutContextValue}>
        <div className="h-full flex flex-col">
          <TopBar
            onMenuAction={handleMenuAction}
            currentProject={currentProject}
            models={models}
            selectedModel={selectedModel}
            onSelectModel={setSelectedModel}
          />

          <WorkspaceTabs
            tabs={tabs}
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            closeTab={closeTab}
          />

          <div className="flex-1 flex overflow-hidden">
            {showSidebar && (
              <div style={{ width: 260, flexShrink: 0 }} className="overflow-hidden">
                <PrimarySidebar
                  onOpenTab={handleOpenTab}
                  activeTab={activeTab}
                  addLog={addLog}
                  onCreateProject={openCreateDialog}
                  currentProject={currentProject}
                  conversations={conversations}
                  currentConvId={convId}
                  onSwitchConversation={handleSwitchConversation}
                  onDeleteConversation={handleDeleteConversation}
                  onNewConversation={handleNewConversation}
                  onOpenCodeTemplates={() => setShowCodeTemplate(true)}
                  onOpenLadderTemplates={() => setShowLadderTemplate(true)}
                  onShowBottom={setShowBottom}
                  onActivateBottomTab={setBottomTab}
                />
              </div>
            )}

            <MainWorkspace
              tabs={tabs}
              activeTab={activeTab}
              openTab={handleOpenTab}
              onCreateProject={openCreateDialog}
              onImportProject={handleImportProjectClick}
              onNewConversation={handleNewConversation}
              currentProject={currentProject}
              conversations={conversations}
              onSwitchConversation={handleSwitchConversation}
              messages={messages}
              onSend={handleSend}
              onStop={handleStop}
              pendingInput={pendingInput}
              sending={sending}
              selectedModel={selectedModel}
              onOpenTemplates={() => setShowTemplates(true)}
              onAddAttachment={() => addLog('info', '[附件] 附件上传功能待接入')}
              addLog={addLog}
              showOrchTutorial={showOrchTutorial}
              onCloseTutorial={() => setShowOrchTutorial(false)}
            />

            {showContext && (
              <div style={{ width: 320, flexShrink: 0 }} className="overflow-hidden">
                <InspectorPanel
                  addLog={addLog}
                  currentProject={currentProject}
                  activeTab={activeTab}
                />
              </div>
            )}
          </div>

          {showBottom && (
            <BottomPanel
              logs={logs}
              collapsed={bottomCollapsed}
              setCollapsed={setBottomCollapsed}
              activeTab={bottomTab}
              setActiveTab={setBottomTab}
            />
          )}

          <input
            ref={importRef}
            type="file"
            accept=".ap18,.ap19,.ap17,.zip"
            onChange={handleImportProject}
            className="hidden"
          />

          {showTemplates && (
            <PromptTemplateModal
              onClose={() => setShowTemplates(false)}
              onSelect={handleTemplateSelect}
            />
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

          {showAbout && (
            <div
              className="fixed inset-0 z-modal-backdrop flex items-center justify-center bg-black/50"
              onClick={() => setShowAbout(false)}
            >
              <div
                className="bg-ide-panel border border-ide-border rounded-lg p-6 w-80 text-center"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="text-lg font-bold text-accent mb-1">AI PLC Assistant</div>
                <div className="text-xs text-text-dim mb-3">v1.0.0</div>
                <div className="text-xs text-text-secondary space-y-1 mb-4">
                  <div>工业自动化 AI 编程工作台</div>
                  <div className="text-text-dim">Electron + React + FastAPI</div>
                  <div className="text-text-dim">ASCII-LAD-V2 梯形图标准</div>
                </div>
                <button
                  type="button"
                  onClick={() => setShowAbout(false)}
                  className="px-4 py-1.5 bg-accent text-white rounded text-xs hover:bg-accent-hover transition-colors"
                >
                  关闭
                </button>
              </div>
            </div>
          )}
        </div>
      </LayoutContext.Provider>
    </ErrorBoundary>
  )
}
