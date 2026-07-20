import MenuBar from './MenuBar'
import GlobalStatusBar from './GlobalStatusBar'

/**
 * TopBar — 顶部区域容器（MenuBar + GlobalStatusBar）
 *
 * 高度 48px（--panel-h-topbar），包含左侧菜单 + 右侧状态栏。
 */
export default function TopBar({
  onMenuAction,
  currentProject,
  models,
  selectedModel,
  onSelectModel,
}) {
  return (
    <header className="h-12 flex items-center bg-ide-panel border-b border-ide-border select-none shrink-0 px-3 gap-2">
      <MenuBar onMenuAction={onMenuAction} />
      <GlobalStatusBar
        currentProject={currentProject}
        models={models}
        selectedModel={selectedModel}
        onSelectModel={onSelectModel}
      />
    </header>
  )
}
