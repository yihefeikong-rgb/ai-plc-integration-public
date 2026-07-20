import React, { useState, useRef, useCallback, useEffect } from 'react'

/**
 * SplitPane — 可调整宽度的分栏面板
 *
 * 用法：
 *   <SplitPane direction="horizontal" initialLeft={260} minLeft={180} maxLeft={480}>
 *     <Sidebar />
 *     <MainContent />
 *   </SplitPane>
 *
 * Props:
 *   direction: 'horizontal' | 'vertical'
 *   initialLeft: 初始左侧/上侧尺寸（px）
 *   minLeft: 最小尺寸
 *   maxLeft: 最大尺寸
 *   storageKey: localStorage 持久化 key（可选）
 */
export default function SplitPane({
  children,
  direction = 'horizontal',
  initialLeft = 260,
  minLeft = 180,
  maxLeft = 480,
  storageKey,
  className = '',
}) {
  const [size, setSize] = useState(() => {
    if (storageKey && typeof localStorage !== 'undefined') {
      const saved = localStorage.getItem(`split_${storageKey}`)
      if (saved) {
        const n = parseInt(saved, 10)
        if (!isNaN(n) && n >= minLeft && n <= maxLeft) return n
      }
    }
    return initialLeft
  })
  const dragging = useRef(false)
  const containerRef = useRef(null)

  const onMouseDown = useCallback((e) => {
    dragging.current = true
    e.preventDefault()
    document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize'
    document.body.style.userSelect = 'none'
  }, [direction])

  const onMouseMove = useCallback((e) => {
    if (!dragging.current || !containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const newSize = direction === 'horizontal'
      ? e.clientX - rect.left
      : e.clientY - rect.top
    const clamped = Math.max(minLeft, Math.min(maxLeft, newSize))
    setSize(clamped)
  }, [direction, minLeft, maxLeft])

  const onMouseUp = useCallback(() => {
    if (dragging.current) {
      dragging.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      if (storageKey && typeof localStorage !== 'undefined') {
        localStorage.setItem(`split_${storageKey}`, String(size))
      }
    }
  }, [size, storageKey])

  useEffect(() => {
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
    return () => {
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }
  }, [onMouseMove, onMouseUp])

  const [left, right] = Array.isArray(children) ? children : [children, null]
  const isH = direction === 'horizontal'

  return (
    <div
      ref={containerRef}
      className={`flex ${isH ? 'flex-row' : 'flex-col'} ${className}`}
      style={{ height: '100%', width: '100%' }}
    >
      <div
        style={isH ? { width: size, flexShrink: 0 } : { height: size, flexShrink: 0 }}
        className="overflow-hidden"
      >
        {left}
      </div>
      <div
        onMouseDown={onMouseDown}
        style={isH
          ? { width: 4, cursor: 'col-resize', flexShrink: 0 }
          : { height: 4, cursor: 'row-resize', flexShrink: 0 }
        }
        className="bg-ide-border hover:bg-accent transition-colors"
        role="separator"
        aria-orientation={isH ? 'vertical' : 'horizontal'}
      />
      <div className="flex-1 overflow-hidden">{right}</div>
    </div>
  )
}
