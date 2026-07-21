import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup, fireEvent } from '@testing-library/react'
import { useRef, useState } from 'react'
import useFocusTrap from './useFocusTrap'

// 测试用组件：弹窗容器 + 外部触发按钮
function TrapHost({ active }) {
  const ref = useRef(null)
  useFocusTrap(ref, active)
  return (
    <div>
      <button data-testid="outside-trigger">外部触发</button>
      <div ref={ref} data-testid="trap-container">
        <button data-testid="first-btn">第一个按钮</button>
        <button data-testid="second-btn">第二个按钮</button>
        <button data-testid="third-btn">第三个按钮</button>
      </div>
    </div>
  )
}

// 可卸载的包装组件，用于测试焦点恢复
function MountableHost() {
  // 初始 mounted=false，点击 open-btn 后才挂载 TrapHost，模拟真实弹窗打开流程
  const [mounted, setMounted] = useState(false)
  return (
    <div>
      <button data-testid="open-btn" onClick={() => setMounted(true)}>
        打开弹窗
      </button>
      <button data-testid="close-btn" onClick={() => setMounted(false)}>
        关闭弹窗
      </button>
      {mounted && <TrapHost active={true} />}
    </div>
  )
}

afterEach(() => {
  cleanup()
})

describe('useFocusTrap', () => {
  it('active 时自动聚焦第一个可聚焦元素', () => {
    const { getByTestId } = render(<TrapHost active={true} />)
    expect(document.activeElement).toBe(getByTestId('first-btn'))
  })

  it('active=false 时不锁定焦点', () => {
    const { getByTestId } = render(<TrapHost active={false} />)
    expect(document.activeElement).not.toBe(getByTestId('first-btn'))
  })

  it('Tab 在最后一个元素时循环到第一个', () => {
    const { getByTestId } = render(<TrapHost active={true} />)
    const third = getByTestId('third-btn')
    third.focus()
    expect(document.activeElement).toBe(third)
    fireEvent.keyDown(third, { key: 'Tab' })
    expect(document.activeElement).toBe(getByTestId('first-btn'))
  })

  it('Shift+Tab 在第一个元素时循环到最后一个', () => {
    const { getByTestId } = render(<TrapHost active={true} />)
    const first = getByTestId('first-btn')
    expect(document.activeElement).toBe(first)
    fireEvent.keyDown(first, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(getByTestId('third-btn'))
  })

  it('Tab 在中间元素时不循环（jsdom 不模拟默认推进）', () => {
    const { getByTestId } = render(<TrapHost active={true} />)
    const second = getByTestId('second-btn')
    second.focus()
    fireEvent.keyDown(second, { key: 'Tab' })
    // 中间元素 Tab 不 preventDefault，jsdom 不模拟默认推进，焦点仍在 second
    expect(document.activeElement).toBe(second)
  })

  it('卸载时恢复焦点到打开前的元素', () => {
    const { getByTestId } = render(<MountableHost />)
    const openBtn = getByTestId('open-btn')
    // 初始 TrapHost 未挂载，焦点可在 openBtn
    openBtn.focus()
    expect(document.activeElement).toBe(openBtn)
    // 点击打开按钮，挂载 TrapHost，useFocusTrap 记录 previouslyFocused=openBtn 并聚焦 first-btn
    fireEvent.click(openBtn)
    expect(document.activeElement).toBe(getByTestId('first-btn'))
    // 卸载 TrapHost，cleanup 应恢复焦点到 openBtn
    fireEvent.click(getByTestId('close-btn'))
    expect(document.activeElement).toBe(openBtn)
  })

  it('containerRef 为 null 时不抛错', () => {
    function NullRefHost() {
      const ref = useRef(null)
      useFocusTrap(ref, true)
      return <div data-testid="no-ref">无 ref</div>
    }
    expect(() => render(<NullRefHost />)).not.toThrow()
  })

  it('非 Tab 键不触发循环逻辑', () => {
    const { getByTestId } = render(<TrapHost active={true} />)
    const first = getByTestId('first-btn')
    expect(document.activeElement).toBe(first)
    fireEvent.keyDown(first, { key: 'Enter' })
    expect(document.activeElement).toBe(first)
  })
})
