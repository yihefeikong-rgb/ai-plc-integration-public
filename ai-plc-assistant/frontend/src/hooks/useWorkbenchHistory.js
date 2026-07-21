import { useState, useCallback } from 'react'

/**
 * 工作台历史记录 — localStorage 持久化
 * 每个工作台独立存储，最多保留 maxItems 条
 */
export default function useWorkbenchHistory(key, maxItems = 20) {
  const storageKey = `wb_history_${key}`

  const [history, setHistory] = useState(() => {
    try { return JSON.parse(localStorage.getItem(storageKey) || '[]') }
    catch (e) {
      // F-070 修复：localStorage 读取失败记录警告
      console.warn(`[useWorkbenchHistory] localStorage.getItem(${storageKey}) 失败:`, e?.message)
      return []
    }
  })

  const save = useCallback((entry) => {
    setHistory(prev => {
      const item = {
        id: Date.now().toString(),
        time: new Date().toLocaleString(),
        ...entry,
      }
      const next = [item, ...prev].slice(0, maxItems)
      try { localStorage.setItem(storageKey, JSON.stringify(next)) }
      catch (e) {
        // F-070 修复：localStorage 写入失败记录警告
        console.warn(`[useWorkbenchHistory] localStorage.setItem(${storageKey}) 失败:`, e?.message)
      }
      return next
    })
  }, [storageKey, maxItems])

  const remove = useCallback((id) => {
    setHistory(prev => {
      const next = prev.filter(e => e.id !== id)
      try { localStorage.setItem(storageKey, JSON.stringify(next)) }
      catch (e) {
        // F-070 修复：localStorage 写入失败记录警告
        console.warn(`[useWorkbenchHistory] localStorage.setItem(${storageKey}) 失败:`, e?.message)
      }
      return next
    })
  }, [storageKey])

  const clear = useCallback(() => {
    setHistory([])
    try { localStorage.removeItem(storageKey) }
    catch (e) {
      // F-070 修复：localStorage 删除失败记录警告
      console.warn(`[useWorkbenchHistory] localStorage.removeItem(${storageKey}) 失败:`, e?.message)
    }
  }, [storageKey])

  return { history, save, remove, clear }
}
