// 程序解析 Inspector — 最近 code 消息统计 + 块类型
import { FileSearch, ListTree, Code2 } from 'lucide-react'
import { PanelSection, KeyValue, findLastMessageByType } from './shared'

// D-3：程序解析 Inspector — 最近 code 消息统计 + 块类型
export default function ParseInspector({ currentProject, messages }) {
  const lastCode = findLastMessageByType(messages, 'code')
  return (
    <>
      <PanelSection title="解析概览" icon={FileSearch}>
        {lastCode ? (
          <div className="space-y-1.5">
            <KeyValue k="语言" v={currentProject?.language || 'SCL'} />
            <KeyValue k="状态" v="已解析" />
          </div>
        ) : (
          <div className="text-xs text-text-dim">尚未解析程序</div>
        )}
      </PanelSection>

      <PanelSection title="块类型" icon={ListTree} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div><span className="text-accent font-mono">OB</span> 组织块（主循环/中断）</div>
          <div><span className="text-accent font-mono">FB</span> 功能块（带背景 DB）</div>
          <div><span className="text-accent font-mono">FC</span> 功能（无背景）</div>
          <div><span className="text-accent font-mono">DB</span> 数据块</div>
        </div>
      </PanelSection>

      <PanelSection title="分析" icon={Code2} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div>· 语法检查</div>
          <div>· 变量引用分析</div>
          <div>· 块调用关系</div>
        </div>
      </PanelSection>
    </>
  )
}
