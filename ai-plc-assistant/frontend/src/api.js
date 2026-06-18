/** 后端 API 通信模块 */

// Dev 模式走 Vite proxy（绕过系统代理），Prod 模式直连后端
export const API_BASE = import.meta.env.DEV ? '/api' : 'http://127.0.0.1:8005/api'

async function request(path, options = {}) {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// ---- 项目管理 ----

export const listProjects = (limit = 50) => request(`/projects?limit=${limit}`)
export const getProject = (id) => request(`/projects/${id}`)
export const createProject = (data) => request('/projects', { method: 'POST', body: JSON.stringify(data) })
export const updateProject = (id, data) => request(`/projects/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const deleteProject = (id) => request(`/projects/${id}`, { method: 'DELETE' })
export async function importProject(file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_BASE}/projects/import`, { method: 'POST', body: formData })
  if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `HTTP ${res.status}`) }
  return res.json()
}

// ---- 对话管理 ----

export const listConversations = (limit = 20) => request(`/conversations?limit=${limit}`)
export const getConversation = (id) => request(`/conversations/${id}`)
export const createConversation = (title = '', model_id = 'deepseek') =>
  request('/conversations', { method: 'POST', body: JSON.stringify({ title, model_id }) })
export const deleteConversation = (id) => request(`/conversations/${id}`, { method: 'DELETE' })
export const addMessage = (convId, role, content, msg_type = 'text', metadata = {}) =>
  request(`/conversations/${convId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ role, content, msg_type, metadata }),
  })

// ---- 知识库 ----

export async function uploadDocument(file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_BASE}/knowledge/import`, { method: 'POST', body: formData })
  if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `HTTP ${res.status}`) }
  return res.json()
}
export const searchKnowledge = (query, limit = 5) => request(`/knowledge/search?q=${encodeURIComponent(query)}&limit=${limit}`)
export const getKnowledgeStatus = () => request('/knowledge/status')
export const listDocuments = () => request('/knowledge/documents')
export const deleteDocument = (id) => fetch(`${API_BASE}/knowledge/documents/${id}`, { method: 'DELETE' }).then(r => r.json())

// ---- PLC 工程搜索 ----

export const searchProjects = (query, typeFilter = '', limit = 20) => {
  let url = `/search?q=${encodeURIComponent(query)}&limit=${limit}`
  if (typeFilter) url += `&type_filter=${typeFilter}`
  return request(url)
}
export const getSearchStats = () => request('/search/stats')
export const indexProjectDir = (directory = '') => {
  let url = `${API_BASE}/search/index`
  if (directory) url += `?directory=${encodeURIComponent(directory)}`
  return fetch(url, { method: 'POST' }).then(r => r.json())
}

// ---- 梯形图生成 ----

export const generateLadder = (input, variables = {}, templateId = '', modelId = 'deepseek') =>
  fetch(`${API_BASE}/generate/ladder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input, variables, template_id: templateId, model_id: modelId }),
  }).then(r => r.json())

export const generateSCL = (input) =>
  fetch(`${API_BASE}/generate/ladder/scl`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input }),
  }).then(r => r.json())

export const exportCode = (data) =>
  fetch(`${API_BASE}/generate/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }).then(r => r.json())

// ---- Prompt 模板 ----

export const listTemplates = (category = '') => {
  let url = '/prompts'
  if (category) url += `?category=${encodeURIComponent(category)}`
  return request(url)
}
export const getTemplate = (id) => request(`/prompts/${id}`)
export const getTemplateCategories = () => request('/prompts/categories')

// ---- 设置 ----

export const getSettings = () => request('/settings')
export const updateSettings = (data) => request('/settings', { method: 'PUT', body: JSON.stringify(data) })
export const getProviders = () => request('/settings/providers')
export const testProvider = (provider) => request(`/settings/test/${provider}`, { method: 'POST' })

// ---- 模型 ----

export const getModels = () => request('/models')

// ---- SSE 流式对话 ----

export async function streamChat({ model_id = 'deepseek', messages = [], temperature, project_context, onToken, onDone, onError, signal }) {
  const body = { model_id, messages }
  if (temperature !== undefined) body.temperature = temperature
  if (project_context) body.project_context = project_context

  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let ragSources = []

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop()

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const payload = line.slice(6).trim()
      if (payload === '[DONE]') return
      try {
        const data = JSON.parse(payload)
        if (data.token) onToken?.(data.token)
        if (data.error) { onError?.(new Error(data.error)); return }
        if (data.rag_sources) ragSources = data.rag_sources
        if (data.done) onDone?.({ ...data, rag_sources: ragSources })
      } catch {}
    }
  }
}

// ---- 代码模板（SCL 文件列表）----

export const listCodeTemplates = () => request('/knowledge/code-templates')
export const getCodeTemplateContent = (name) => request(`/knowledge/code-templates/${encodeURIComponent(name)}`)

// ---- 健康检查 ----

export const healthCheck = () => request('/health')
