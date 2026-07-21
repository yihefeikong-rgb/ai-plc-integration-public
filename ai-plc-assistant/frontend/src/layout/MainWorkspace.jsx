import ChatArea from '../components/chat/ChatArea'
import Dashboard from '../components/Dashboard'
import CodeExplainer from '../components/CodeExplainer'
import IoTableGenerator from '../components/IoTableGenerator'
import FaultDiagnosis from '../components/FaultDiagnosis'
import LadderGenerator from '../components/LadderGenerator'
import VariableAnalyzer from '../components/VariableAnalyzer'
import SettingsPanel from '../components/SettingsPanel'
import OrchestratorPanel from '../components/orchestrator/OrchestratorPanel'
import RobotPanel from '../components/RobotPanel'

/**
 * MainWorkspace — 主工作区
 *
 * 从 App.jsx 88-100 + 134-138 行迁移。
 * 已打开 tab 保持挂载（display:none 隐藏），切走不丢状态。
 */
export default function MainWorkspace({
  tabs,
  activeTab,
  openTab,
  onCreateProject,
  onImportProject,
  onNewConversation,
  currentProject,
  conversations,
  onSwitchConversation,
  messages,
  onSend,
  onStop,
  pendingInput,
  sending,
  selectedModel,
  onOpenTemplates,
  onAddAttachment,
  addLog,
  showOrchTutorial,
  onCloseTutorial,
}) {
  const workspaces = {
    welcome: (
      <Dashboard
        onOpenTab={openTab}
        onCreateProject={onCreateProject}
        onImportProject={onImportProject}
        onNewConversation={onNewConversation}
        currentProject={currentProject}
        conversations={conversations}
        onSwitchConversation={onSwitchConversation}
      />
    ),
    chat: (
      <ChatArea
        messages={messages}
        onSend={onSend}
        onStop={onStop}
        initialInput={pendingInput}
        sending={sending}
        currentProject={currentProject}
        selectedModel={selectedModel}
        onOpenTemplates={onOpenTemplates}
        onAddAttachment={onAddAttachment}
      />
    ),
    parse: <CodeExplainer addLog={addLog} selectedModel={selectedModel} />,
    'io-table': <IoTableGenerator addLog={addLog} selectedModel={selectedModel} />,
    diagnose: <FaultDiagnosis addLog={addLog} selectedModel={selectedModel} />,
    ladder: <LadderGenerator addLog={addLog} selectedModel={selectedModel} />,
    variables: <VariableAnalyzer addLog={addLog} selectedModel={selectedModel} />,
    settings: <SettingsPanel addLog={addLog} />,
    orchestrator: (
      <OrchestratorPanel
        showTutorial={showOrchTutorial}
        onCloseTutorial={onCloseTutorial}
      />
    ),
    robot: <RobotPanel currentProject={currentProject} />,
  }

  return (
    <div className="flex-1 flex overflow-hidden">
      {tabs.map((tab) =>
        workspaces[tab.id] ? (
          <div
            key={tab.id}
            style={{ display: activeTab === tab.id ? 'flex' : 'none' }}
            className="flex-1 overflow-hidden"
          >
            {workspaces[tab.id]}
          </div>
        ) : null,
      )}
    </div>
  )
}
