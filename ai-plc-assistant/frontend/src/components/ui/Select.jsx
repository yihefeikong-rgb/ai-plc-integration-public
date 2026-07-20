import React from 'react'

/**
 * Select — 下拉选择框
 *
 * 用法：
 *   <Select value={v} onChange={e => setV(e.target.value)}>
 *     <option value="a">A</option>
 *     <option value="b">B</option>
 *   </Select>
 */
export default function Select({
  value,
  onChange,
  children,
  disabled = false,
  className = '',
  name,
  id,
  ...rest
}) {
  return (
    <select
      value={value}
      onChange={onChange}
      disabled={disabled}
      name={name}
      id={id}
      className={`select ${className}`}
      {...rest}
    >
      {children}
    </select>
  )
}
