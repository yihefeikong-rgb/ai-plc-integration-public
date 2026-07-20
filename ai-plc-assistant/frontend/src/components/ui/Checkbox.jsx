import React from 'react'

/**
 * Checkbox — 复选框
 *
 * 用法：
 *   <Checkbox checked={v} onChange={e => setV(e.target.checked)} label="启用" />
 */
export default function Checkbox({
  checked,
  onChange,
  label,
  disabled = false,
  className = '',
  name,
  id,
}) {
  return (
    <label
      className={`inline-flex items-center gap-2 text-xs ${
        disabled ? 'text-text-dim cursor-not-allowed' : 'text-text-secondary cursor-pointer'
      } ${className}`}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        name={name}
        id={id}
        className="w-3 h-3 accent-[var(--color-accent)] cursor-pointer"
      />
      {label && <span>{label}</span>}
    </label>
  )
}
