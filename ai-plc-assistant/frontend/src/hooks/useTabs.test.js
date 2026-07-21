import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import useTabs from './useTabs'

describe('useTabs', () => {
  it('initializes with welcome tab active', () => {
    const { result } = renderHook(() => useTabs())
    expect(result.current.tabs).toEqual([{ id: 'welcome', closable: false }])
    expect(result.current.activeTab).toBe('welcome')
  })

  it('openTab adds new tab and switches active', () => {
    const { result } = renderHook(() => useTabs())
    act(() => result.current.openTab('chat'))
    expect(result.current.tabs).toEqual([
      { id: 'welcome', closable: false },
      { id: 'chat', closable: true },
    ])
    expect(result.current.activeTab).toBe('chat')
  })

  it('openTab does not duplicate existing tab but still switches active', () => {
    const { result } = renderHook(() => useTabs())
    act(() => result.current.openTab('chat'))
    act(() => result.current.openTab('welcome'))
    expect(result.current.tabs.length).toBe(2)
    expect(result.current.activeTab).toBe('welcome')
  })

  it('closeTab removes tab and switches to last remaining', () => {
    const { result } = renderHook(() => useTabs())
    act(() => result.current.openTab('chat'))
    act(() => result.current.openTab('ladder'))
    act(() => result.current.closeTab('ladder'))
    expect(result.current.tabs.find((t) => t.id === 'ladder')).toBeUndefined()
    // F-033/F-037 回归：closeTab 后 activeTab 应切到最后一个，不应是已关闭的 ladder
    expect(result.current.activeTab).toBe('chat')
  })

  it('closeTab on non-active tab does not change activeTab', () => {
    const { result } = renderHook(() => useTabs())
    act(() => result.current.openTab('chat'))
    act(() => result.current.openTab('ladder'))
    act(() => result.current.closeTab('chat'))
    expect(result.current.activeTab).toBe('ladder')
  })

  it('closeTab on active last tab falls back to welcome', () => {
    const { result } = renderHook(() => useTabs())
    act(() => result.current.openTab('chat'))
    // 关闭 chat（当前激活），只剩 welcome
    act(() => result.current.closeTab('chat'))
    expect(result.current.activeTab).toBe('welcome')
  })

  it('F-033 stale closure 回归：连续 closeTab 两次不切回已关闭 tab', () => {
    const { result } = renderHook(() => useTabs())
    act(() => result.current.openTab('chat'))
    act(() => result.current.openTab('ladder'))
    act(() => result.current.openTab('variables'))
    // 连续关闭 ladder 和 variables（同一批 act 内模拟快速连点）
    act(() => {
      result.current.closeTab('variables')
      result.current.closeTab('ladder')
    })
    // 最终 tabs 应只剩 welcome + chat
    expect(result.current.tabs.map((t) => t.id).sort()).toEqual(['chat', 'welcome'])
    // activeTab 应是 chat（最后一个剩余的），不应停留在已关闭的 variables/ladder
    expect(result.current.activeTab).toBe('chat')
  })

  it('welcome tab is not closable', () => {
    const { result } = renderHook(() => useTabs())
    const welcomeTab = result.current.tabs.find((t) => t.id === 'welcome')
    expect(welcomeTab.closable).toBe(false)
  })
})
