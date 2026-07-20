import React from 'react'
import PanelHeader from './PanelHeader'

/**
 * Panel — 面板容器
 *
 * 用法：
 *   <Panel title="系统状态" icon={Server}>内容</Panel>
 *   <Panel header={<CustomHeader />}>内容</Panel>
 */
export default function Panel({
  children,
  title,
  icon,
  header,
  className = '',
  bodyClassName = '',
  noBody = false,
  ...rest
}) {
  return (
    <div className={`panel ${className}`} {...rest}>
      {(header || title) && (
        <PanelHeader icon={icon} title={title}>
          {header}
        </PanelHeader>
      )}
      {!noBody && <div className={`panel-body ${bodyClassName}`}>{children}</div>}
      {noBody && children}
    </div>
  )
}
