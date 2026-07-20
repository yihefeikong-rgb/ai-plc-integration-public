import { useState, useEffect, useCallback, useRef } from 'react'
import {
  createConversation, addMessage, getConversation, listConversations, deleteConversation,
  generateLadder, streamChat, API_BASE,
} from '../api'

const isGenerationRequest = (text) => {
  const t = text.toLowerCase()
  // 只有明确要求梯形图/ladder 时才走结构化生成路径
  // "写程序"/"编写"等通用请求走 SSE 流式对话
  return t.includes('梯形图') || t.includes('ladder')
}

export default function useConversation({ addLog, openTab, selectedModel, currentProject }) {
  const [convId, setConvId] = useState(null)
  const [conversations, setConversations] = useState([])
  const [messages, setMessages] = useState([])
  const [sending, setSending] = useState(false)
  const [pendingInput, setPendingInput] = useState('')
  const streamContentRef = useRef('')
  const abortRef = useRef(null)

  const refreshConversations = useCallback(async () => {
    try {
      const d = await listConversations(20)
      setConversations(d.conversations || [])
    } catch {}
  }, [])

  useEffect(() => { refreshConversations() }, [refreshConversations])

  // Batch 6：组件卸载时中止进行中的请求，避免对已卸载组件 setState
  useEffect(() => {
    return () => { abortRef.current?.abort() }
  }, [])

  const ensureConversation = useCallback(async (title) => {
    if (convId) return convId
    try {
      const d = await createConversation(title || 'AI 对话', selectedModel)
      const newId = d.conversation.id
      setConvId(newId)
      refreshConversations()
      return newId
    } catch { return null }
  }, [convId, selectedModel, refreshConversations])

  const handleNewConversation = useCallback(async () => {
    setConvId(null)
    setMessages([])
    openTab('chat')
    addLog('info', '[对话] 新建')
  }, [openTab, addLog])

  const handleSwitchConversation = useCallback(async (id) => {
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
  }, [openTab, addLog])

  const handleDeleteConversation = useCallback(async (id) => {
    try {
      await deleteConversation(id)
      if (convId === id) {
        setConvId(null)
        setMessages([])
      }
      refreshConversations()
      addLog('info', '[对话] 已删除')
    } catch (err) { addLog('error', `[对话] 删除失败: ${err.message}`) }
  }, [convId, refreshConversations, addLog])

  const handleSend = useCallback(async (text) => {
    if (sending) return
    openTab('chat')
    setMessages(prev => [...prev, { role: 'user', content: text }])
    addLog('info', `[发送] ${text.slice(0, 50)}...`)
    setSending(true)

    // Batch 6：AbortController 支持停止生成
    const controller = new AbortController()
    abortRef.current = controller

    const cid = await ensureConversation(text.slice(0, 30))
    if (cid) addMessage(cid, 'user', text).catch(() => {})

    try {
      // 梯形图生成（非流式）
      if (isGenerationRequest(text)) {
        try {
          const result = await generateLadder(text, {}, '', selectedModel, controller.signal)
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

      // LLM 流式调用（SSE 失败自动回退非流式）
      const chatMessages = [...messages.slice(-6).map(m => ({ role: m.role, content: m.content })),
        { role: 'user', content: text }]
      const projCtx = currentProject ? {
        name: currentProject.name, plc_type: currentProject.plc_type,
        tia_version: currentProject.tia_version, language: currentProject.language,
      } : undefined

      try {
        addLog('info', `[LLM] ${selectedModel} (streaming)`)
        streamContentRef.current = ''
        setMessages(prev => [...prev, { role: 'assistant', content: '', streaming: true }])

        await streamChat({
          model_id: selectedModel,
          messages: chatMessages,
          project_context: projCtx,
          signal: controller.signal,
          onToken: (token) => {
            streamContentRef.current += token
            const content = streamContentRef.current
            setMessages(prev => {
              const updated = [...prev]
              updated[updated.length - 1] = { ...updated[updated.length - 1], content }
              return updated
            })
          },
          onDone: (data) => {
            const finalContent = streamContentRef.current
            setMessages(prev => {
              const updated = [...prev]
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                streaming: false,
                rag_sources: data?.rag_sources,
                model: data?.model,
                fallback: data?.fallback,
              }
              return updated
            })
            if (data?.fallback) {
              addLog('warn', `[LLM] 主模型不可用，已切换到 ${data.model}`)
            }
            addLog('info', `[LLM] ${data?.model || selectedModel} — ${finalContent.length}字`)
            if (cid) addMessage(cid, 'assistant', finalContent).catch(() => {})
          },
          onError: (err) => {
            addLog('error', `[SSE 错误] ${err.message}`)
            setMessages(prev => {
              const updated = [...prev]
              updated[updated.length - 1] = {
                role: 'assistant', content: `调用失败: ${err.message}`, streaming: false,
              }
              return updated
            })
          },
        })
      } catch (streamErr) {
        // 用户主动停止
        if (controller.signal.aborted) {
          addLog('info', '[LLM] 用户停止生成')
          setMessages(prev => {
            const updated = [...prev]
            if (updated[updated.length - 1]?.streaming) {
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                streaming: false,
                stopped: true,
              }
            }
            return updated
          })
          setSending(false)
          return
        }
        // SSE 失败 → 回退到非流式
        addLog('warn', `[SSE] 流式连接失败, 回退非流式: ${streamErr.message}`)
        try {
          const res = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model_id: selectedModel, messages: chatMessages, project_context: projCtx }),
            signal: controller.signal,
          })
          if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`)
          const data = await res.json()
          if (data.fallback) addLog('warn', `[LLM] 已切换到 ${data.model}`)
          addLog('info', `[LLM] ${data.model} — ${data.content.length}字 (非流式)`)
          setMessages(prev => {
            const updated = [...prev]
            updated[updated.length - 1] = {
              role: 'assistant', content: data.content, streaming: false, rag_sources: data.rag_sources,
              model: data.model, fallback: data.fallback,
            }
            return updated
          })
          if (cid) addMessage(cid, 'assistant', data.content).catch(() => {})
        } catch (fallbackErr) {
          addLog('error', `[错误] ${fallbackErr.message}`)
          setMessages(prev => {
            const updated = [...prev]
            updated[updated.length - 1] = {
              role: 'assistant', content: `调用失败: ${fallbackErr.message}`, streaming: false,
            }
            return updated
          })
        }
      }
    } catch (err) {
      addLog('error', `[错误] ${err.message}`)
      setMessages(prev => [...prev, { role: 'assistant', content: `调用失败: ${err.message}` }])
    }
    abortRef.current = null
    setSending(false)
  }, [sending, openTab, addLog, selectedModel, messages, ensureConversation, currentProject])

  // Batch 6：停止生成
  const handleStop = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
      addLog('info', '[LLM] 用户请求停止生成')
    }
  }, [addLog])

  return {
    convId, conversations, messages, sending, pendingInput,
    setPendingInput, handleNewConversation, handleSwitchConversation, handleDeleteConversation, handleSend, handleStop, refreshConversations,
  }
}
