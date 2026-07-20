import React, { useState, useRef, useEffect, createContext, useContext } from 'react'

/**
 * DropdownMenu — 下拉菜单（Compound Component）
 *
 * 用法：
 *   <DropdownMenu label="项目" onAction={a => handle(a)}>
 *     <DropdownMenu.Item action="project:new" shortcut="Ctrl+N">新建项目</DropdownMenu.Item>
 *     <DropdownMenu.Separator />
 *     <DropdownMenu.Item action="project:settings">项目设置</DropdownMenu.Item>
 *   </DropdownMenu>
 */

const MenuContext = createContext(null)

export default function DropdownMenu({ label, items, onAction, children }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleAction = (action) => {
    setOpen(false)
    onAction?.(action)
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={`px-3 py-1 text-xs rounded transition-colors ${
          open ? 'bg-ide-active text-text-primary' : 'text-text-secondary hover:text-text-primary hover:bg-ide-hover'
        }`}
      >
        {label}
      </button>
      {open && (
        <MenuContext.Provider value={{ handleAction }}>
          <div className="absolute left-0 top-full mt-0.5 bg-ide-sidebar border border-ide-border rounded shadow-xl z-dropdown min-w-[200px] py-1">
            {children || (items || []).map((item, i) =>
              item.separator ? (
                <div key={i} className="my-1 border-t border-ide-border" />
              ) : (
                <Item
                  key={i}
                  action={item.action}
                  shortcut={item.shortcut}
                  disabled={item.disabled}
                >
                  {item.label}
                </Item>
              ),
            )}
          </div>
        </MenuContext.Provider>
      )}
    </div>
  )
}

function Item({ action, children, shortcut, disabled = false }) {
  const ctx = useContext(MenuContext)
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => ctx?.handleAction(action)}
      className={`w-full text-left px-4 py-1.5 text-xs flex items-center justify-between ${
        disabled
          ? 'text-text-dim cursor-not-allowed'
          : 'text-text-secondary hover:bg-accent/15 hover:text-text-primary'
      }`}
    >
      <span>{children}</span>
      {shortcut && <span className="text-text-dim text-2xs ml-6">{shortcut}</span>}
    </button>
  )
}

function Separator() {
  return <div className="my-1 border-t border-ide-border" />
}

DropdownMenu.Item = Item
DropdownMenu.Separator = Separator
