// 故障诊断 Inspector — 最近 warning/error + 排查步骤
import { AlertTriangle, ListTree, Cpu } from 'lucide-react'
import { PanelSection, KeyValue } from './shared'

// D-3：故障诊断 Inspector — 最近 warning/error + 排查步骤
export default function DiagnoseInspector({ messages }) {
  const warnings = messages.filter(m => m.type === 'warning' || m.error)
  const lastWarn = warnings[warnings.length - 1]

  return (
    <>
      <PanelSection title="诊断概览" icon={AlertTriangle}>
        {lastWarn ? (
          <div className="space-y-1.5">
            <KeyValue k="告警数" v={warnings.length} />
            <KeyValue k="最近" v={lastWarn.content?.slice(0, 30) + '...'} mono={false} />
          </div>
        ) : (
          <div className="text-xs text-text-dim">暂无告警</div>
        )}
      </PanelSection>

      <PanelSection title="排查步骤" icon={ListTree} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div>1. 检查 PLC 电源与连接</div>
          <div>2. 验证 IO 信号</div>
          <div>3. 查看诊断缓冲区</div>
          <div>4. 分析程序逻辑</div>
          <div>5. 检查网络通信</div>
        </div>
      </PanelSection>

      <PanelSection title="设备状态" icon={Cpu} defaultOpen={false}>
        <div className="text-2xs text-text-dim">待接入 PLC 状态 API</div>
      </PanelSection>
    </>
  )
}
