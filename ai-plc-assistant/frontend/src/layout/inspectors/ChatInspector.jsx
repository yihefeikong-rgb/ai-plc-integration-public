// AI 助手 Inspector — 当前模型 + 项目上下文 + 最近对话 + 知识库引用
import { useMemo } from 'react'
import { Bot, Cpu, History, BookOpen } from 'lucide-react'
import { PanelSection, KeyValue } from './shared'

// D-3：AI 助手 Inspector — 当前模型 + 项目上下文 + 最近对话 + 知识库引用
export default function ChatInspector({ currentProject, selectedModel, messages, conversations }) {
  const lastAiMsg = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant') return messages[i]
    }
    return null
  }, [messages])
  const ragSources = lastAiMsg?.rag_sources || []
  const recentConvs = (conversations || []).slice(0, 5)

  return (
    <>
      <PanelSection title="当前模型" icon={Bot}>
        <div className="space-y-1.5">
          <KeyValue k="模型" v={selectedModel || '未选择'} />
          <KeyValue k="流式" v="SSE" />
          <KeyValue k="停止" v="AbortController" />
        </div>
      </PanelSection>

      <PanelSection title="项目上下文" icon={Cpu}>
        {currentProject ? (
          <div className="space-y-1.5">
            <KeyValue k="项目" v={currentProject.name} />
            <KeyValue k="PLC" v={currentProject.plc_type} />
            <KeyValue k="TIA" v={currentProject.tia_version} />
            <KeyValue k="语言" v={currentProject.language} />
          </div>
        ) : (
          <div className="text-xs text-text-dim">未选择项目，AI 助手将不携带项目上下文</div>
        )}
      </PanelSection>

      <PanelSection title="最近对话" icon={History} defaultOpen={false}>
        {recentConvs.length > 0 ? (
          <div className="space-y-1">
            {recentConvs.map((c) => (
              <div key={c.id} className="text-2xs text-text-secondary truncate p-1 hover:bg-ide-hover rounded">
                {c.title || '未命名对话'}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-text-dim">暂无对话</div>
        )}
      </PanelSection>

      <PanelSection title="知识库引用" icon={BookOpen} defaultOpen={false}>
        {ragSources.length > 0 ? (
          <div className="space-y-1">
            {ragSources.map((src, i) => (
              <div key={src.id || src.url || i} className="text-2xs p-1.5 bg-ide-panel rounded border border-ide-border">
                <div className="text-accent font-mono truncate">#{i + 1} {src.title || src.name}</div>
                {src.snippet && <div className="text-text-dim mt-0.5 line-clamp-2">{src.snippet}</div>}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-text-dim">当前对话未引用知识库</div>
        )}
      </PanelSection>
    </>
  )
}
