import { useState, useEffect, useCallback, useRef } from 'react'
import {
  createConversation, addMessage, getConversation, listConversations, deleteConversation,
  generateLadder, streamChat, API_BASE, localControlHeaders,
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
  // F-044 修复：流式会话序号；新建/切换/删除对话时递增，使旧流的回调失效，防止写入错误会话
  const streamSessionRef = useRef(0)
  // F-044 修复：onToken 节流定时器句柄，避免每个 token 触发整树重渲染
  const tokenFlushRef = useRef(null)
  // F-044 修复：messages 镜像，避免 handleSend 因依赖 messages 而随每次 token 重建
  const messagesRef = useRef(messages)
  messagesRef.current = messages
  // F-040：stable key 计数器，避免数组索引 key 导致的 DOM 复用错误
  const msgIdRef = useRef(0)
  const nextMsgId = useCallback(() => `msg-${++msgIdRef.current}`, [])

  const refreshConversations = useCallback(async () => {
    try {
      const d = await listConversations(20)
      setConversations(d.conversations || [])
    } catch (e) {
      // F-070 修复：listConversations 失败时记录警告，不静默吞错
      console.warn('[useConversation] listConversations 失败:', e?.message)
    }
  }, [])

  useEffect(() => { refreshConversations() }, [refreshConversations])

  // Batch 6：组件卸载时中止进行中的请求，避免对已卸载组件 setState
  useEffect(() => {
    return () => {
      abortRef.current?.abort()
      if (tokenFlushRef.current) clearTimeout(tokenFlushRef.current)
    }
  }, [])

  const ensureConversation = useCallback(async (title) => {
    if (convId) return convId
    const d = await createConversation(title || 'AI 对话', selectedModel)
    const newId = d.conversation.id
    setConvId(newId)
    refreshConversations()
    return newId
  }, [convId, selectedModel, refreshConversations])

  const handleNewConversation = useCallback(async () => {
    // F-044 修复：新建对话前中止并失效进行中的流，防止回调写入新对话或空列表
    streamSessionRef.current += 1
    abortRef.current?.abort()
    abortRef.current = null
    setConvId(null)
    setMessages([])
    openTab('chat')
    addLog('info', '[对话] 新建')
  }, [openTab, addLog])

  const handleSwitchConversation = useCallback(async (id) => {
    // F-044 修复：切换对话前中止并失效进行中的流，防止回调写入目标对话
    streamSessionRef.current += 1
    abortRef.current?.abort()
    abortRef.current = null
    try {
      const d = await getConversation(id)
      const conv = d.conversation
      setConvId(conv.id)
      setMessages(conv.messages.map(m => ({
        id: nextMsgId(),
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
        // F-044 修复：删除当前对话时同样中止并失效进行中的流
        streamSessionRef.current += 1
        abortRef.current?.abort()
        abortRef.current = null
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
    setMessages(prev => [...prev, { id: nextMsgId(), role: 'user', content: text }])
    addLog('info', `[发送] ${text.slice(0, 50)}...`)
    setSending(true)

    // Batch 6：AbortController 支持停止生成
    const controller = new AbortController()
    abortRef.current = controller
    // F-044 修复：本次流式会话序号，回调据此判断流是否已失效
    const session = ++streamSessionRef.current

    let cid
    try {
      // F-044 修复：对话创建失败不再静默吞掉，fail-closed 中止本次发送
      cid = await ensureConversation(text.slice(0, 30))
    } catch (e) {
      addLog('error', `[对话] 创建失败: ${e.message}`)
      setMessages(prev => [...prev, { id: nextMsgId(), role: 'assistant', content: `对话创建失败，请重试: ${e.message}`, error: true }])
      abortRef.current = null
      setSending(false)
      return
    }
    // F-044 修复：创建期间流已被新建/切换/删除失效时，中止本次发送
    if (streamSessionRef.current !== session) {
      abortRef.current = null
      setSending(false)
      return
    }
    // F-044 修复：落库失败不再静默丢弃，向用户告警
    addMessage(cid, 'user', text).catch(e => addLog('warn', `[持久化] 用户消息保存失败: ${e?.message}`))

    try {
      // 梯形图生成（非流式）
      if (isGenerationRequest(text)) {
        try {
          const result = await generateLadder(text, {}, '', selectedModel, controller.signal)
          if (result.structured?.networks?.length > 0) {
            addLog('info', `[生成] ${result.title} (${result.mode})`)
            setMessages(prev => [...prev, {
              id: nextMsgId(), role: 'assistant', type: 'ladder',
              title: result.title, description: result.description,
              structured: result.structured, content: result.text, mode: result.mode,
            }])
            addMessage(cid, 'assistant', result.text, 'ladder').catch(e => addLog('warn', `[持久化] 梯形图保存失败: ${e?.message}`))
            setSending(false)
            return
          }
        } catch { addLog('warn', '[生成] 回退 LLM') }
      }

      // LLM 流式调用（SSE 失败自动回退非流式）
      const chatMessages = [...messagesRef.current.slice(-6).map(m => ({ role: m.role, content: m.content })),
        { role: 'user', content: text }]
      const projCtx = currentProject ? {
        name: currentProject.name, plc_type: currentProject.plc_type,
        tia_version: currentProject.tia_version, language: currentProject.language,
      } : undefined

      try {
        addLog('info', `[LLM] ${selectedModel} (streaming)`)
        streamContentRef.current = ''
        setMessages(prev => [...prev, { id: nextMsgId(), role: 'assistant', content: '', streaming: true }])

        // F-044 修复：节流 flush —— 仅更新末条 streaming 消息，且仅在会话未失效时写入
        const flushToken = () => {
          const content = streamContentRef.current
          if (streamSessionRef.current !== session) return
          setMessages(prev => {
            if (!prev.length) return prev
            const last = prev[prev.length - 1]
            if (!last?.streaming) return prev
            return [...prev.slice(0, -1), { ...last, content }]
          })
        }

        await streamChat({
          model_id: selectedModel,
          messages: chatMessages,
          project_context: projCtx,
          signal: controller.signal,
          onToken: (token) => {
            // F-044 修复：会话失效后忽略迟到 token，禁止写入新对话/空列表
            if (streamSessionRef.current !== session) return
            streamContentRef.current += token
            // F-044 修复：合并 token 写入，避免每个 token 触发整树重渲染
            if (tokenFlushRef.current) return
            tokenFlushRef.current = setTimeout(flushToken, 40)
          },
          onDone: (data) => {
            if (tokenFlushRef.current) { clearTimeout(tokenFlushRef.current); tokenFlushRef.current = null }
            // F-044 修复：会话失效后不再改写新对话状态，也不持久化到旧 cid
            if (streamSessionRef.current !== session) return
            const finalContent = streamContentRef.current
            setMessages(prev => {
              if (!prev.length) return prev
              const last = prev[prev.length - 1]
              if (!last?.streaming) return prev
              return [...prev.slice(0, -1), {
                ...last,
                id: last?.id || nextMsgId(),
                content: finalContent,
                streaming: false,
                rag_sources: data?.rag_sources,
                model: data?.model,
                fallback: data?.fallback,
              }]
            })
            if (data?.fallback) {
              addLog('warn', `[LLM] 主模型不可用，已切换到 ${data.model}`)
            }
            addLog('info', `[LLM] ${data?.model || selectedModel} — ${finalContent.length}字`)
            addMessage(cid, 'assistant', finalContent).catch(e => addLog('warn', `[持久化] 助手回复保存失败: ${e?.message}`))
          },
          onError: (err) => {
            if (tokenFlushRef.current) { clearTimeout(tokenFlushRef.current); tokenFlushRef.current = null }
            // F-044 修复：会话失效后忽略迟到的错误回调
            if (streamSessionRef.current !== session) return
            addLog('error', `[SSE 错误] ${err.message}`)
            // F-039 修复：保留已 streaming 出来的半截内容，追加错误提示而非替换
            const partialContent = streamContentRef.current
            setMessages(prev => {
              if (!prev.length) return prev
              const last = prev[prev.length - 1]
              if (!last?.streaming) return prev
              const keptContent = partialContent || last?.content || ''
              const errorSuffix = `\n\n[调用失败: ${err.message}]`
              return [...prev.slice(0, -1), {
                ...last,
                id: last?.id || nextMsgId(),
                role: 'assistant',
                content: keptContent ? `${keptContent}${errorSuffix}` : errorSuffix.trim(),
                streaming: false,
                error: true,
              }]
            })
          },
        })
      } catch (streamErr) {
        if (tokenFlushRef.current) { clearTimeout(tokenFlushRef.current); tokenFlushRef.current = null }
        // 用户主动停止
        if (controller.signal.aborted) {
          addLog('info', '[LLM] 用户停止生成')
          setMessages(prev => {
            const updated = [...prev]
            if (updated[updated.length - 1]?.streaming) {
              const last = updated[updated.length - 1]
              updated[updated.length - 1] = {
                ...last,
                id: last?.id || nextMsgId(),
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
            // F-042 修复：与 streamChat 主路径一致，注入 localControlHeaders
            headers: { ...localControlHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ model_id: selectedModel, messages: chatMessages, project_context: projCtx }),
            signal: controller.signal,
          })
          if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`)
          const data = await res.json()
          // 修复：非流式回退响应先校验 content 字段，缺失或非字符串时 fail-closed 抛出
          // 明确错误，避免 data.content.length 抛 TypeError 把成功请求误判为失败，
          // 并把原始 JS 错误文本渲染为用户可见的 [调用失败: ...] 气泡与日志
          if (typeof data?.content !== 'string') {
            throw new Error('服务端响应缺少 content 字段（非流式回退）')
          }
          if (data.fallback) addLog('warn', `[LLM] 已切换到 ${data.model}`)
          addLog('info', `[LLM] ${data.model} — ${data.content.length}字 (非流式)`)
          // F-044 修复：仅当末条仍是本会话的 streaming 消息时才改写，防止写入新对话
          setMessages(prev => {
            if (!prev.length) return prev
            const last = prev[prev.length - 1]
            if (!last?.streaming) return prev
            return [...prev.slice(0, -1), {
              id: last?.id || nextMsgId(),
              role: 'assistant', content: data.content, streaming: false, rag_sources: data.rag_sources,
              model: data.model, fallback: data.fallback,
            }]
          })
          addMessage(cid, 'assistant', data.content).catch(e => addLog('warn', `[持久化] 助手回复保存失败: ${e?.message}`))
        } catch (fallbackErr) {
          // F-044 修复：用户主动停止（fallback 阶段）与 SSE 主路径一致，不渲染错误
          if (controller.signal.aborted) {
            addLog('info', '[LLM] 用户停止生成')
            setMessages(prev => {
              const updated = [...prev]
              if (updated[updated.length - 1]?.streaming) {
                const last = updated[updated.length - 1]
                updated[updated.length - 1] = {
                  ...last,
                  id: last?.id || nextMsgId(),
                  streaming: false,
                  stopped: true,
                }
              }
              return updated
            })
          } else {
            addLog('error', `[错误] ${fallbackErr.message}`)
            // F-039 修复：非流式 fallback 失败也保留半截内容
            const partialContent = streamContentRef.current
            setMessages(prev => {
              if (!prev.length) return prev
              const last = prev[prev.length - 1]
              if (!last?.streaming) return prev
              const keptContent = partialContent || last?.content || ''
              const errorSuffix = `\n\n[调用失败: ${fallbackErr.message}]`
              return [...prev.slice(0, -1), {
                id: last?.id || nextMsgId(),
                role: 'assistant',
                content: keptContent ? `${keptContent}${errorSuffix}` : errorSuffix.trim(),
                streaming: false,
                error: true,
              }]
            })
          }
        }
      }
    } catch (err) {
      addLog('error', `[错误] ${err.message}`)
      setMessages(prev => {
        // F-044 修复：会话失效后不向新对话追加错误消息
        if (streamSessionRef.current !== session) return prev
        return [...prev, { id: nextMsgId(), role: 'assistant', content: `调用失败: ${err.message}`, error: true }]
      })
    }
    if (tokenFlushRef.current) { clearTimeout(tokenFlushRef.current); tokenFlushRef.current = null }
    abortRef.current = null
    setSending(false)
  }, [sending, openTab, addLog, selectedModel, ensureConversation, currentProject])

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
