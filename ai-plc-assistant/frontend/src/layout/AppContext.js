import { createContext, useContext } from 'react'

/**
 * LayoutContext — 应用外壳全局动作入口
 *
 * 仅承载 4 个值，避免 prop drilling：
 * - openTab(id, data): 打开工作区 tab（或处理特殊 id 如 'project'/'templates'）
 * - addLog(level, message): 记录日志
 * - activeTab: 当前激活的 tab id
 * - registerModal(name): 打开指定 Modal
 */
export const LayoutContext = createContext(null)

export function useLayout() {
  const ctx = useContext(LayoutContext)
  if (!ctx) {
    throw new Error('useLayout must be used within <LayoutContext.Provider>')
  }
  return ctx
}

export const MODALS = {
  PROMPT_TEMPLATE: 'promptTemplate',
  CODE_TEMPLATE: 'codeTemplate',
  LADDER_TEMPLATE: 'ladderTemplate',
  CREATE_PROJECT: 'createProject',
  ABOUT: 'about',
}
