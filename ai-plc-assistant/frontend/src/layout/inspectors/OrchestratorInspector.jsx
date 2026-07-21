// 编排 Inspector — 编排说明 + 工具数
// F-050 修复：接 orchestratorHealth() 真实状态，不再硬编码"运行中"
// F-050a 设计选择：Inspector 切 tab 时单次查询，不做 15s 轮询。
// 理由：Inspector 是临时查看面板，用户切走 tab 后不再需要状态；
//       GlobalStatusBar 是常驻状态栏才需要 15s 轮询保持实时。
//       如未来需要 Inspector 也实时刷新，可加 setInterval 但需注意切 tab 后清理。
import { useState, useEffect } from 'react'
import { Server, ListTree, Bot } from 'lucide-react'
import { orchestratorHealth } from '../../api'
import { PanelSection, KeyValue } from './shared'

// D-3：编排 Inspector — 编排说明 + 工具数
export default function OrchestratorInspector() {
  const [orchHealth, setOrchHealth] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    orchestratorHealth()
      .then((d) => { if (!cancelled) setOrchHealth(d) })
      .catch(() => { if (!cancelled) setOrchHealth(null) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const connected = orchHealth?.servers_connected > 0
  const statusText = loading
    ? '查询中…'
    : connected
      ? `已连接 ${orchHealth.servers_connected} 个`
      : '未连接'

  return (
    <>
      <PanelSection title="编排概览" icon={Server}>
        <div className="space-y-1.5">
          <KeyValue k="服务器" v="orchestrator" />
          <KeyValue k="协议" v="MCP stdio" />
          <KeyValue k="状态" v={statusText} />
        </div>
      </PanelSection>

      <PanelSection title="工作流" icon={ListTree} defaultOpen={false}>
        <div className="text-2xs text-text-dim mb-1.5">以下为系统内置示例工作流，实际可用列表以编排层返回为准。</div>
        <div className="text-2xs text-text-secondary space-y-1">
          <div>· P3 流水线（5 步）</div>
          <div>· TIA 工程态流水线</div>
          <div>· 运行态控制闭环</div>
        </div>
      </PanelSection>

      <PanelSection title="Agent" icon={Bot} defaultOpen={false}>
        <div className="text-2xs text-text-dim">Agent 列表待接入，当前编排层 /orchestrator/health 未返回 Agent 信息。</div>
      </PanelSection>
    </>
  )
}
