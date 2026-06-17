/** 后端 API 通信模块 */

const API_BASE = 'http://127.0.0.1:8005/api'

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

// ---- 健康检查 ----

export const healthCheck = () => request('/health')
