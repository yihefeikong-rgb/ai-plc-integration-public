import { useState, useEffect } from 'react'
import { Save, Key, Cpu, Check, Loader2, Zap, CircleCheck, CircleX } from 'lucide-react'
import { getSettings, updateSettings, getProviders, testProvider } from '../api'

// 前端 fallback — 即使后端没启动也能显示卡片
const FALLBACK_PROVIDERS = {
  deepseek: {
    label: 'DeepSeek',
    base_url: 'https://api.deepseek.com/v1',
    models: ['deepseek-v4-flash', 'deepseek-v4-pro'],
    default: 'deepseek-v4-flash',
  },
  openai: {
    label: 'OpenAI',
    base_url: 'https://api.openai.com/v1',
    models: ['gpt-5.5', 'gpt-5.5-pro', 'gpt-5.4-mini', 'gpt-5.4-nano', 'gpt-4.1', 'gpt-4.1-mini'],
    default: 'gpt-5.5',
  },
  kimi: {
    label: 'Kimi (月之暗面)',
    base_url: 'https://api.moonshot.ai/v1',
    models: ['kimi-k2.7-code', 'kimi-k2.7-code-highspeed', 'kimi-k2.6', 'kimi-k2.5', 'moonshot-v1-128k'],
    default: 'kimi-k2.7-code',
  },
  claude: {
    label: 'Claude (Anthropic)',
    base_url: 'https://api.anthropic.com',
    models: ['claude-opus-4-8', 'claude-sonnet-4-6', 'claude-opus-4-7', 'claude-haiku-4-5'],
    default: 'claude-sonnet-4-6',
  },
  custom: {
    label: '自定义模型',
    base_url: '',
    models: [],
    default: '',
  },
}

const PROVIDER_ORDER = ['deepseek', 'openai', 'kimi', 'claude', 'custom']
const plcTypes = ['S7-1200', 'S7-1500', 'S7-300', 'S7-400']
const tiaVersions = ['V15', 'V16', 'V17', 'V18', 'V19']
const languages = ['SCL', 'LAD', 'FBD', 'STL']

function ProviderCard({ id, info, form, set, onTest, testResult, testing }) {
  const keyField = `${id}_api_key`
  const urlField = `${id}_base_url`
  const modelField = `${id}_model`
  const isCustom = id === 'custom'

  return (
    <div className="border border-ide-border rounded p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-text-primary">{info.label}</div>
        <button onClick={() => onTest(id)} disabled={testing}
          className="flex items-center gap-1.5 px-3 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent disabled:opacity-50 transition-colors text-text-secondary">
          {testing ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
          {testing ? '测试中...' : '测试连接'}
        </button>
      </div>

      {testResult && (
        <div className={`flex items-center gap-2 px-3 py-2 rounded text-xs ${
          testResult.status === 'ok'
            ? 'bg-status-ok/10 text-status-ok border border-status-ok/20'
            : 'bg-status-error/10 text-status-error border border-status-error/20'
        }`}>
          {testResult.status === 'ok' ? <CircleCheck size={14} /> : <CircleX size={14} />}
          <span className="flex-1">{testResult.message}</span>
          {testResult.reply && <span className="text-2xs opacity-70">"{testResult.reply}"</span>}
        </div>
      )}

      {/* API Key */}
      <div className="flex items-center gap-3">
        <label className="text-xs text-text-dim w-20 shrink-0">API Key</label>
        <input type="password" value={form[keyField] || ''} onChange={e => set(keyField, e.target.value)}
          placeholder="sk-..."
          className="flex-1 bg-ide-input border border-ide-border rounded px-3 py-1.5 text-xs text-text-primary placeholder-text-dim outline-none focus:border-accent font-mono" />
      </div>

      {/* Base URL */}
      <div className="flex items-center gap-3">
        <label className="text-xs text-text-dim w-20 shrink-0">Base URL</label>
        <input type="text" value={form[urlField] || info.base_url || ''} onChange={e => set(urlField, e.target.value)}
          placeholder={isCustom ? 'https://your-api.com/v1' : ''}
          className="flex-1 bg-ide-input border border-ide-border rounded px-3 py-1.5 text-xs text-text-primary placeholder-text-dim outline-none focus:border-accent font-mono" />
      </div>

      {/* Model */}
      <div className="flex items-center gap-3">
        <label className="text-xs text-text-dim w-20 shrink-0">模型</label>
        {isCustom || !info.models?.length ? (
          // 自定义：自由输入
          <input type="text" value={form[modelField] || ''} onChange={e => set(modelField, e.target.value)}
            placeholder="模型名称，如 my-model-v1"
            className="flex-1 bg-ide-input border border-ide-border rounded px-3 py-1.5 text-xs text-text-primary placeholder-text-dim outline-none focus:border-accent font-mono" />
        ) : (
          // 预设：下拉选择
          <select value={form[modelField] || info.default || ''}
            onChange={e => set(modelField, e.target.value)}
            style={{ color: '#CCCCCC', backgroundColor: '#3C3C3C' }}
            className="flex-1 border border-ide-border rounded px-3 py-1.5 text-xs outline-none focus:border-accent">
            {info.models.map(m => (
              <option key={m} value={m} style={{ color: '#CCCCCC', backgroundColor: '#3C3C3C' }}>
                {m}{m === info.default ? ' (推荐)' : ''}
              </option>
            ))}
          </select>
        )}
      </div>
    </div>
  )
}

export default function SettingsPanel({ addLog }) {
  const [form, setForm] = useState({})
  const [providers, setProviders] = useState(FALLBACK_PROVIDERS)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)
  const [testResults, setTestResults] = useState({})
  const [testingId, setTestingId] = useState('')

  useEffect(() => {
    Promise.all([
      getSettings().then(d => setForm(d.settings || {})).catch(() => {}),
      getProviders().then(d => {
        if (d.providers && Object.keys(d.providers).length > 0) {
          setProviders({ ...FALLBACK_PROVIDERS, ...d.providers })
        }
      }).catch(() => {}),
    ]).finally(() => setLoading(false))
  }, [])

  const set = (key, val) => setForm(prev => ({ ...prev, [key]: val }))

  const handleSave = async () => {
    setSaving(true)
    setSaved(false)
    try {
      const d = await updateSettings(form)
      setForm(d.settings || form)
      setSaved(true)
      addLog?.('info', '[设置] 保存成功')
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      addLog?.('error', `[设置] ${err.message}`)
    }
    setSaving(false)
  }

  const handleTest = async (provider) => {
    setTestingId(provider)
    setTestResults(prev => ({ ...prev, [provider]: null }))
    try { await updateSettings(form) } catch {}
    try {
      const result = await testProvider(provider)
      setTestResults(prev => ({ ...prev, [provider]: result }))
      addLog?.('info', `[测试] ${provider}: ${result.message}`)
    } catch (err) {
      setTestResults(prev => ({ ...prev, [provider]: { status: 'error', message: err.message } }))
    }
    setTestingId('')
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-text-dim text-sm">
        <Loader2 size={16} className="animate-spin mr-2" /> 加载设置...
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-8 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-lg font-semibold text-text-bright">设置</h1>
        <button onClick={handleSave} disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-accent text-white rounded text-xs font-medium hover:bg-accent-hover disabled:opacity-50 transition-colors">
          {saving ? <Loader2 size={14} className="animate-spin" /> : saved ? <Check size={14} /> : <Save size={14} />}
          {saving ? '保存中...' : saved ? '已保存' : '保存设置'}
        </button>
      </div>

      {/* 模型配置 */}
      <div className="bg-ide-sidebar border border-ide-border rounded mb-6">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-ide-border">
          <Key size={15} className="text-accent" />
          <h3 className="text-sm font-medium text-text-primary">模型 API 配置</h3>
        </div>
        <div className="p-4 space-y-3">
          {PROVIDER_ORDER.map(id => {
            const info = providers[id] || FALLBACK_PROVIDERS[id]
            if (!info) return null
            return (
              <ProviderCard key={id} id={id} info={info} form={form} set={set}
                onTest={handleTest} testResult={testResults[id]} testing={testingId === id} />
            )
          })}
        </div>
      </div>

      {/* PLC 默认配置 */}
      <div className="bg-ide-sidebar border border-ide-border rounded mb-6">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-ide-border">
          <Cpu size={15} className="text-accent" />
          <h3 className="text-sm font-medium text-text-primary">PLC 默认配置</h3>
        </div>
        <div className="p-4 space-y-3">
          {[
            { label: 'PLC 型号', key: 'default_plc_type', options: plcTypes, fallback: 'S7-1200' },
            { label: 'TIA 版本', key: 'default_tia_version', options: tiaVersions, fallback: 'V18' },
            { label: '编程语言', key: 'default_language', options: languages, fallback: 'SCL' },
          ].map(f => (
            <div key={f.key} className="flex items-center gap-3">
              <label className="text-xs text-text-dim w-20 shrink-0">{f.label}</label>
              <select value={form[f.key] || f.fallback} onChange={e => set(f.key, e.target.value)}
                style={{ color: '#CCCCCC', backgroundColor: '#3C3C3C' }}
                className="border border-ide-border rounded px-3 py-1.5 text-xs outline-none focus:border-accent">
                {f.options.map(o => (
                  <option key={o} value={o} style={{ color: '#CCCCCC', backgroundColor: '#3C3C3C' }}>{o}</option>
                ))}
              </select>
            </div>
          ))}
        </div>
      </div>

      <button onClick={handleSave} disabled={saving}
        className="flex items-center gap-2 px-4 py-2 bg-accent text-white rounded text-xs font-medium hover:bg-accent-hover disabled:opacity-50 transition-colors">
        {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
        {saving ? '保存中...' : '保存设置'}
      </button>
    </div>
  )
}
