import { useState, useEffect, useCallback } from 'react'
import { X } from 'lucide-react'
import Toolbar from './components/Toolbar'
import Sidebar from './components/Sidebar'
import Dashboard from './components/Dashboard'
import ChatArea from './components/ChatArea'
import ContextPanel from './components/ContextPanel'
import LogPanel from './components/LogPanel'
import PromptTemplateModal from './components/PromptTemplateModal'
import SettingsPanel from './components/SettingsPanel'
import CodeExplainer from './components/CodeExplainer'
import {
  getModels, generateLadder, createProject,
  createConversation, addMessage, getConversation, listConversations,
} from './api'

const API_BASE = 'http://127.0.0.1:8005/api'

const TAB_LABELS = {
  welcome: '欢迎',
  chat: 'AI 助手',
  ladder: '梯形图生成',
  parse: '程序解析',
  diagnose: '故障诊断',
  'io-table': 'IO表生成',
  variables: '变量分析',
  settings: '设置',
}

export default function App() {
  const [tabs, setTabs] = useState([{ id: 'welcome', closable: false }])
  const [activeTab, setActiveTab] = useState('welcome')
  const [messages, setMessages] = useState([])
  const [sending, setSending] = useState(false)
  const [pendingInput, setPendingInput] = useState('')
  const [models, setModels] = useState([{ id: 'deepseek', name: 'DeepSeek', enabled: true }])
  const [selectedModel, setSelectedModel] = useState('deepseek')
  const [logs, setLogs] = useState([
    { time: new Date().toLocaleTimeString(), level: 'info', message: '系统已启动' },
  ])
  const [showTemplates, setShowTemplates] = useState(false)
  const [currentProject, setCurrentProject] = useState(null)
  const [convId, setConvId] = useState(null)
  const [conversations, setConversations] = useState([])
  const [showSidebar, setShowSidebar] = useState(true)
  const [showContext, setShowContext] = useState(true)
  const [showBottom, setShowBottom] = useState(true)

  // 启动时加载模型和对话列表
  useEffect(() => {
    getModels().then(d => {
      if (d.models) {
        setModels(d.models)
        const enabled = d.models.find(m => m.enabled)
        if (enabled) setSelectedModel(enabled.id)
      }
    }).catch(() => {})

    refreshConversations()
  }, [])

  const refreshConversations = async () => {
    try {
      const d = await listConversations(20)
      setConversations(d.conversations || [])
    } catch {}
  }

  const addLog = useCallback((level, message) => {
    setLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), level, message }])
  }, [])

  // Tab 管理
  const openTab = (id, data) => {
    if (id === 'templates') { setShowTemplates(true); return }
    if (id === 'project' && data) {
      setCurrentProject(data)
      addLog('info', `[项目] ${data.name}`)
      return
    }
    if (!tabs.find(t => t.id === id)) {
      setTabs(prev => [...prev, { id, closable: true }])
    }
    setActiveTab(id)
  }

  const closeTab = (id) => {
    const next = tabs.filter(t => t.id !== id)
    setTabs(next)
    if (activeTab === id) setActiveTab(next[next.length - 1]?.id || 'welcome')
  }

  // 项目管理
  const handleCreateProject = async () => {
    const name = prompt('项目名称：')
    if (!name) return
    try {
      const d = await createProject({ name })
      setCurrentProject(d.project)
      addLog('info', `[项目] 创建: ${name}`)
    } catch (err) { addLog('error', `[项目] ${err.message}`) }
  }

  // 对话管理
  const handleNewConversation = async () => {
    setConvId(null)
    setMessages([])
    openTab('chat')
    addLog('info', '[对话] 新建')
  }

  const handleSwitchConversation = async (id) => {
    try {
      const d = await getConversation(id)
      const conv = d.conversation
      setConvId(conv.id)
      setMessages(conv.messages.map(m => ({
        role: m.role,
        content: m.content,
        type: m.msg_type === 'ladder' ? 'ladder' : undefined,
      })))
      openTab('chat')
      addLog('info', `[对话] 切换: ${conv.title}`)
    } catch (err) { addLog('error', `[对话] ${err.message}`) }
  }

  const ensureConversation = async () => {
    if (convId) return convId
    try {
      const d = await createConversation('AI 对话', selectedModel)
      const newId = d.conversation.id
      setConvId(newId)
      refreshConversations()
      return newId
    } catch { return null }
  }

  // 发送消息
  const isGenerationRequest = (text) =>
    ['生成', '梯形图', 'ladder', '程序', '编写'].some(k => text.includes(k))

  const handleSend = async (text) => {
    if (sending) return
    openTab('chat')
    setMessages(prev => [...prev, { role: 'user', content: text }])
    addLog('info', `[发送] ${text.slice(0, 50)}...`)
    setSending(true)

    const cid = await ensureConversation()
    if (cid) addMessage(cid, 'user', text).catch(() => {})

    try {
      // 梯形图生成
      if (isGenerationRequest(text)) {
        try {
          const result = await generateLadder(text, {}, '', selectedModel)
          if (result.structured?.networks?.length > 0) {
            addLog('info', `[生成] ${result.title} (${result.mode})`)
            setMessages(prev => [...prev, {
              role: 'assistant', type: 'ladder',
              title: result.title, description: result.description,
              structured: result.structured, content: result.text, mode: result.mode,
            }])
            if (cid) addMessage(cid, 'assistant', result.text, 'ladder').catch(() => {})
            setSending(false)
            return
          }
        } catch { addLog('warn', '[生成] 回退 LLM') }
      }

      // LLM 调用
      addLog('info', `[LLM] ${selectedModel}`)
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_id: selectedModel,
          messages: [...messages.slice(-6).map(m => ({ role: m.role, content: m.content })),
            { role: 'user', content: text }],
        }),
      })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`)

      const data = await res.json()
      if (data.fallback) {
        addLog('warn', `[LLM] 主模型不可用，已切换到 ${data.model}`)
      }
      addLog('info', `[LLM] ${data.model} — ${data.content.length}字`)
      setMessages(prev => [...prev, { role: 'assistant', content: data.content, rag_sources: data.rag_sources }])
      if (cid) addMessage(cid, 'assistant', data.content).catch(() => {})
    } catch (err) {
      addLog('error', `[错误] ${err.message}`)
      setMessages(prev => [...prev, { role: 'assistant', content: `调用失败: ${err.message}` }])
    }
    setSending(false)
  }

  const handleTemplateSelect = (content) => {
    setPendingInput(content)
    openTab('chat')
  }

  const handleMenuAction = (action) => {
    switch (action) {
      case 'project:new': handleCreateProject(); break
      case 'project:import': openTab('chat'); setPendingInput('导入工程文件'); break
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

  const renderWorkspace = () => {
    switch (activeTab) {
      case 'welcome':
        return <Dashboard onOpenTab={openTab} onCreateProject={handleCreateProject} />
      case 'parse':
        return <CodeExplainer addLog={addLog} />
      case 'settings':
        return <SettingsPanel addLog={addLog} />
      case 'chat':
      case 'ladder':
      case 'diagnose':
      case 'io-table':
      case 'variables':
        return <ChatArea messages={messages} onSend={handleSend} initialInput={pendingInput} sending={sending} />
      default:
        return <Dashboard onOpenTab={openTab} onCreateProject={handleCreateProject} />
    }
  }

  return (
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
          <Sidebar onOpenTab={openTab} activeTab={activeTab} addLog={addLog}
            onCreateProject={handleCreateProject} currentProject={currentProject}
            conversations={conversations} currentConvId={convId}
            onSwitchConversation={handleSwitchConversation} onNewConversation={handleNewConversation} />
        )}
        {renderWorkspace()}
        {showContext && <ContextPanel addLog={addLog} currentProject={currentProject} />}
      </div>

      {showBottom && <LogPanel logs={logs} />}

      {showTemplates && (
        <PromptTemplateModal onClose={() => setShowTemplates(false)} onSelect={handleTemplateSelect} />
      )}
    </div>
  )
}
