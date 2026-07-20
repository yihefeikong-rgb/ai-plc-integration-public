import React, { useState, useRef } from 'react'

/**
 * Tooltip — 悬浮提示
 *
 * 用法：
 *   <Tooltip content="点击新建项目" placement="bottom">
 *     <button>新建</button>
 *   </Tooltip>
 *
 * 注意：触发器必须是单个子元素且能接收 onMouseEnter/onMouseLeave。
 */
export default function Tooltip({
  content,
  children,
  placement = 'top',
  delay = 100,
  className = '',
}) {
  const [visible, setVisible] = useState(false)
  const timerRef = useRef(null)

  const show = () => {
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setVisible(true), delay)
  }
  const hide = () => {
    clearTimeout(timerRef.current)
    setVisible(false)
  }

  const positionClass = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-1',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-1',
    left: 'right-full top-1/2 -translate-y-1/2 mr-1',
    right: 'left-full top-1/2 -translate-y-1/2 ml-1',
  }[placement]

  return (
    <span className="relative inline-flex" onMouseEnter={show} onMouseLeave={hide}>
      {children}
      {visible && content && (
        <span className={`tooltip ${positionClass} ${className}`} role="tooltip">
          {content}
        </span>
      )}
    </span>
  )
}
