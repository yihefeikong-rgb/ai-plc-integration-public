// ConfirmationsInspector — 人工审批面板：AI 发起的危险操作请求在此批准/拒绝
//
// 流程：AI 工作流（如 nl_to_plcsim）执行危险操作前创建审批请求 →
// 本面板列出待审批请求 → 人工点"批准"签发一次性通行证 →
// 用户带 request_id 重新执行工作流，AI 领取通行证后继续。
import { useEffect, useCallback, useState } from 'react'
import { RefreshCw, ShieldCheck, ShieldX, ShieldQuestion } from 'lucide-react'
import { API_BASE, localControlHeaders } from '../../api'

const STATUS_META = {
  pending: { label: '待审批', icon: ShieldQuestion, cls: 'text-amber-400 bg-amber-500/10 border-amber-500/30' },
  approved: { label: '已批准', icon: ShieldCheck, cls: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' },
  denied: { label: '已拒绝', icon: ShieldX, cls: 'text-red-400 bg-red-500/10 border-red-500/30' },
}

function fmtTime(ts) {
  if (!ts) return '—'
  const d = new Date(ts * 1000)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export default function ConfirmationsInspector({ addLog }) {
  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(false)
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/orchestrator/confirmations/requests`, {
        headers: localControlHeaders(),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setRequests(data.requests || [])
    } catch (err) {
      addLog?.(`审批请求加载失败: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }, [addLog])

  useEffect(() => { load() }, [load])

  async function act(id, action) {
    setBusyId(id)
    try {
      const res = await fetch(`${API_BASE}/api/orchestrator/confirmations/requests/${id}/${action}`, {
        method: 'POST', headers: localControlHeaders(),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      addLog?.(`审批请求 ${id} 已${action === 'approve' ? '批准（一次性通行证已签发）' : '拒绝'}`)
      await load()
    } catch (err) {
      addLog?.(`处理审批请求失败: ${err.message}`)
    } finally {
      setBusyId(null)
    }
  }

  const pendingCount = requests.filter((r) => r.status === 'pending').length

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-ide-border">
        <div className="flex items-center gap-2 text-xs font-semibold">
          <ShieldQuestion size={14} className="text-amber-400" />
          <span>人工审批</span>
          {pendingCount > 0 && (
            <span className="px-1.5 py-0.5 text-2xs rounded bg-amber-500/15 text-amber-400">
              {pendingCount} 待批
            </span>
          )}
        </div>
        <button
          onClick={load}
          className="p-1 text-text-dim hover:text-text-secondary disabled:opacity-40"
          disabled={loading}
          title="刷新"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {requests.length === 0 && !loading && (
          <div className="text-center text-2xs text-text-dim py-8">
            暂无审批请求。
            <br />
            AI 执行危险操作（如下载程序）时会在这里出现待批请求。
          </div>
        )}

        {requests.map((r) => {
          const meta = STATUS_META[r.status] || STATUS_META.pending
          const Icon = meta.icon
          const busy = busyId === r.request_id
          return (
            <div key={r.request_id} className="border border-ide-border rounded-md p-2.5 space-y-1.5 bg-ide-bg/50">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-2xs text-text-secondary truncate">{r.request_id}</span>
                <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-2xs rounded border ${meta.cls}`}>
                  <Icon size={11} />
                  {meta.label}
                </span>
              </div>
              <div className="text-xs font-medium text-text-primary">{r.workflow_name}</div>
              {r.description && (
                <div className="text-2xs text-text-dim line-clamp-2">{r.description}</div>
              )}
              <div className="text-2xs text-text-dim">
                发起时间 {fmtTime(r.created_at)}
                {r.approver ? ` · 处理人 ${r.approver}` : ''}
              </div>

              {r.status === 'pending' && (
                <div className="flex items-center gap-1.5 pt-1">
                  <button
                    onClick={() => act(r.request_id, 'approve')}
                    disabled={busy}
                    className="flex-1 inline-flex items-center justify-center gap-1 px-2 py-1 text-2xs rounded bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-600/30 disabled:opacity-40"
                  >
                    <ShieldCheck size={12} />
                    {busy ? '处理中…' : '批准'}
                  </button>
                  <button
                    onClick={() => act(r.request_id, 'deny')}
                    disabled={busy}
                    className="flex-1 inline-flex items-center justify-center gap-1 px-2 py-1 text-2xs rounded bg-red-600/10 text-red-400 border border-red-500/20 hover:bg-red-600/20 disabled:opacity-40"
                  >
                    <ShieldX size={12} />
                    拒绝
                  </button>
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className="px-3 py-2 border-t border-ide-border text-2xs text-text-dim leading-relaxed">
        批准后会签发一张 <span className="text-text-secondary">5 分钟有效、一次性</span> 的通行证。
        用户需携带返回的 request_id 重新执行工作流。
      </div>
    </div>
  )
}
