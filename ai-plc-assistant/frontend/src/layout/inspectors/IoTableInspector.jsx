// IO 表 Inspector — 最近 io-table 消息统计 + 地址范围 + 分类
import { Table2, ListTree, AlertCircle } from 'lucide-react'
import { PanelSection, KeyValue, findLastMessageByType, parseContent } from './shared'

// D-3：IO 表 Inspector — 最近 io-table 消息统计 + 地址范围 + 分类
export default function IoTableInspector({ currentProject, messages }) {
  const lastIo = findLastMessageByType(messages, 'io-table')
  const data = parseContent(lastIo?.content)
  const rows = data.rows || data.io || data.devices || []

  return (
    <>
      <PanelSection title="IO 表概览" icon={Table2}>
        {rows.length > 0 ? (
          <div className="space-y-1.5">
            <KeyValue k="设备数" v={rows.length} />
            <KeyValue k="输入点" v={rows.filter(r => r.direction === 'input' || r.type === 'I').length} />
            <KeyValue k="输出点" v={rows.filter(r => r.direction === 'output' || r.type === 'Q').length} />
          </div>
        ) : (
          <div className="text-xs text-text-dim">尚未生成 IO 表</div>
        )}
      </PanelSection>

      <PanelSection title="地址范围" icon={ListTree} defaultOpen={false}>
        <div className="text-2xs text-text-dim mb-1.5">以下为 S7-1200 默认示例，实际范围依 PLC 型号与 IO 表生成结果而定。</div>
        <div className="text-2xs text-text-secondary space-y-1">
          <div><span className="text-accent font-mono">I0.0 ~ I0.7</span> 输入区（示例）</div>
          <div><span className="text-accent font-mono">Q0.0 ~ Q0.7</span> 输出区（示例）</div>
          <div><span className="text-accent font-mono">M0.0 ~ M14.7</span> 标志位（示例）</div>
          <div><span className="text-accent font-mono">T0 ~ T9</span> 定时器（示例）</div>
          <div><span className="text-accent font-mono">C0 ~ C9</span> 计数器（示例）</div>
        </div>
      </PanelSection>

      <PanelSection title="校验" icon={AlertCircle} defaultOpen={false}>
        <div className="text-2xs text-text-dim">校验功能待接入，当前 IO 表生成接口未返回校验结果。</div>
        <div className="text-2xs text-text-secondary space-y-1 mt-1.5">
          <div>· 地址冲突检测（待接入）</div>
          <div>· 重复分配检测（待接入）</div>
          <div>· 类型匹配校验（待接入）</div>
        </div>
      </PanelSection>
    </>
  )
}
