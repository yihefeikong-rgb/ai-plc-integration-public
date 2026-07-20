import { useEffect } from 'react'

/**
 * useFocusTrap — 弹窗焦点锁定（F-015，主计划 §11.4 可访问性）
 *
 * 弹窗打开时：
 * - 自动聚焦第一个可聚焦元素
 * - Tab/Shift+Tab 在容器内循环，不跳到弹窗外
 * - 卸载时恢复焦点到打开前的元素
 *
 * 用法：
 *   const containerRef = useRef(null)
 *   useFocusTrap(containerRef, isVisible)
 *   return <div ref={containerRef}>...</div>
 *
 * @param {RefObject<HTMLElement>} containerRef - 弹窗容器 ref
 * @param {boolean} active - 是否激活焦点锁定（弹窗可见时为 true）
 */
export default function useFocusTrap(containerRef, active = true) {
  useEffect(() => {
    if (!active || !containerRef.current) return
    const container = containerRef.current
    const previouslyFocused = document.activeElement

    const getFocusable = () =>
      container.querySelectorAll(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )

    // 聚焦第一个可聚焦元素
    const focusable = getFocusable()
    if (focusable.length > 0) focusable[0].focus()

    const handleKeyDown = (e) => {
      if (e.key !== 'Tab') return
      const items = getFocusable()
      if (items.length === 0) return
      const first = items[0]
      const last = items[items.length - 1]
      if (e.shiftKey) {
        if (document.activeElement === first || !container.contains(document.activeElement)) {
          e.preventDefault()
          last.focus()
        }
      } else {
        if (document.activeElement === last || !container.contains(document.activeElement)) {
          e.preventDefault()
          first.focus()
        }
      }
    }

    container.addEventListener('keydown', handleKeyDown)
    return () => {
      container.removeEventListener('keydown', handleKeyDown)
      if (previouslyFocused && typeof previouslyFocused.focus === 'function') {
        previouslyFocused.focus()
      }
    }
  }, [containerRef, active])
}
