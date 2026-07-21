// 设置 Inspector — 当前项目配置摘要
import { Settings as SettingsIcon, Server, Code2 } from 'lucide-react'
import { PanelSection, KeyValue } from './shared'

// D-3：设置 Inspector — 当前项目配置摘要
export default function SettingsInspector({ currentProject }) {
  return (
    <>
      <PanelSection title="项目配置" icon={SettingsIcon}>
        {currentProject ? (
          <div className="space-y-1.5">
            <KeyValue k="项目名" v={currentProject.name} />
            <KeyValue k="PLC" v={currentProject.plc_type} />
            <KeyValue k="TIA" v={currentProject.tia_version} />
            <KeyValue k="语言" v={currentProject.language} />
          </div>
        ) : (
          <div className="text-xs text-text-dim">未选择项目</div>
        )}
      </PanelSection>

      <PanelSection title="API 配置" icon={Server} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div>· API_BASE 环境变量优先</div>
          <div>· DEV 模式走 vite proxy</div>
          <div>· 生产模式 VITE_API_BASE</div>
        </div>
      </PanelSection>

      <PanelSection title="快捷键" icon={Code2} defaultOpen={false}>
        <div className="text-2xs text-text-secondary space-y-1">
          <div><span className="text-accent font-mono">Ctrl+B</span> — 切换侧栏</div>
          <div><span className="text-accent font-mono">Ctrl+J</span> — 切换底部面板</div>
          <div><span className="text-accent font-mono">Ctrl+`</span> — 切换 Inspector</div>
          <div><span className="text-accent font-mono">Esc</span> — 关闭弹窗</div>
        </div>
      </PanelSection>
    </>
  )
}
