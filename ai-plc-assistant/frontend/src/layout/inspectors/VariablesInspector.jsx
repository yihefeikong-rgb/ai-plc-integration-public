// 变量分析 Inspector — 最近 variables 消息统计 + 命名规范
import { Variable, ListTree, Cpu } from 'lucide-react'
import { PanelSection, KeyValue, findLastMessageByType, parseContent } from './shared'

// D-3：变量分析 Inspector — 最近 variables 消息统计 + 命名规范
export default function VariablesInspector({ currentProject, messages }) {
  const lastVars = findLastMessageByType(messages, 'variables')
  const data = parseContent(lastVars?.content)
  const vars = data.variables || data.rows || data.vars || []

  return (
    <>
      <PanelSection title="变量概览" icon={Variable}>
        {vars.length > 0 ? (
          <div className="space-y-1.5">
            <KeyValue k="变量数" v={vars.length} />
            <KeyValue k="Bool" v={vars.filter(v => v.data_type === 'Bool').length} />
            <KeyValue k="Int" v={vars.filter(v => v.data_type === 'Int').length} />
            <KeyValue k="Real" v={vars.filter(v => v.data_type === 'Real').length} />
          </div>
        ) : (
          <div className="text-xs text-text-dim">尚未分析变量</div>
        )}
      </PanelSection>

      <PanelSection title="命名规范" icon={ListTree} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div>· <span className="text-accent font-mono">bXxx</span> — Bool</div>
          <div>· <span className="text-accent font-mono">iXxx</span> — Int</div>
          <div>· <span className="text-accent font-mono">rXxx</span> — Real</div>
          <div>· <span className="text-accent font-mono">sXxx</span> — String</div>
        </div>
      </PanelSection>

      <PanelSection title="地址分配" icon={Cpu} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div>· M0.0 ~ M14.7 — 标志位</div>
          <div>· MW20 ~ MW40 — Int</div>
          <div>· MD60 ~ MD100 — Real</div>
        </div>
      </PanelSection>
    </>
  )
}
