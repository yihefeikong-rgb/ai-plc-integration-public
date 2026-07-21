// 梯形图 Inspector — 最近 ladder 消息统计 + Network 列表 + 导出格式
import { Zap, ListTree, FileText, Cpu } from 'lucide-react'
import { PanelSection, KeyValue, findLastMessageByType } from './shared'

// D-3：梯形图 Inspector — 最近 ladder 消息统计 + Network 列表 + 导出格式
export default function LadderInspector({ currentProject, messages }) {
  const lastLadder = findLastMessageByType(messages, 'ladder')
  const structured = lastLadder?.structured
  const networks = structured?.networks || []
  const variables = structured?.variables || []

  return (
    <>
      <PanelSection title="梯形图概览" icon={Zap}>
        {lastLadder ? (
          <div className="space-y-1.5">
            <KeyValue k="标题" v={lastLadder.title} mono={false} />
            <KeyValue k="Networks" v={networks.length} />
            <KeyValue k="变量数" v={variables.length} />
            <KeyValue k="模式" v={lastLadder.mode} />
          </div>
        ) : (
          <div className="text-xs text-text-dim">尚未生成梯形图</div>
        )}
      </PanelSection>

      <PanelSection title="Network 列表" icon={ListTree} defaultOpen={false}>
        {networks.length > 0 ? (
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {networks.map((n, i) => (
              <div key={n.number || i} className="text-2xs p-1.5 bg-ide-panel rounded border border-ide-border">
                <div className="flex items-center gap-1">
                  <span className="font-mono text-accent">N{n.number}</span>
                  <span className="text-text-primary truncate flex-1">{n.title}</span>
                </div>
                {n.comment && <div className="text-text-dim mt-0.5 truncate">// {n.comment}</div>}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-text-dim">无 Network</div>
        )}
      </PanelSection>

      <PanelSection title="导出格式" icon={FileText} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div><span className="text-accent font-mono">SCL</span> — 结构化文本</div>
          <div><span className="text-accent font-mono">XML</span> — TIA Portal 导入</div>
          <div><span className="text-accent font-mono">CSV</span> — 变量表</div>
          <div><span className="text-accent font-mono">HMI</span> — 人机界面变量</div>
        </div>
      </PanelSection>

      <PanelSection title="PLC 规范" icon={Cpu} defaultOpen={false}>
        <div className="space-y-1.5">
          <KeyValue k="PLC 类型" v={currentProject?.plc_type || 'S7-1200'} />
          <KeyValue k="TIA 版本" v={currentProject?.tia_version || 'V18'} />
        </div>
      </PanelSection>
    </>
  )
}
