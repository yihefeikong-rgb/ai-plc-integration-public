import React, { forwardRef } from 'react'

/**
 * Input — 单行输入框
 *
 * 用法：
 *   <Input value={v} onChange={e => setV(e.target.value)} placeholder="..." />
 *   <Input type="password" label="API Key" />
 */
const Input = forwardRef(function Input(
  {
    value,
    onChange,
    onKeyDown,
    placeholder,
    type = 'text',
    disabled = false,
    readOnly = false,
    autoFocus = false,
    className = '',
    name,
    id,
    ...rest
  },
  ref,
) {
  return (
    <input
      ref={ref}
      type={type}
      value={value}
      onChange={onChange}
      onKeyDown={onKeyDown}
      placeholder={placeholder}
      disabled={disabled}
      readOnly={readOnly}
      autoFocus={autoFocus}
      name={name}
      id={id}
      className={`input ${className}`}
      {...rest}
    />
  )
})

export default Input
