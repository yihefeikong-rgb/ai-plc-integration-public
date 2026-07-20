import { useEffect } from 'react'

/**
 * useEscClose — Esc 键关闭弹窗（Batch 8，主计划 §11.4）
 *
 * 用法：在弹窗组件顶部调用 useEscClose(onClose)
 * 自动监听 keydown Escape，触发 onClose，卸载时清理监听。
 *
 * @param {Function} onClose - 关闭回调
 */
export default function useEscClose(onClose) {
  useEffect(() => {
    if (!onClose) return
    const handler = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])
}
