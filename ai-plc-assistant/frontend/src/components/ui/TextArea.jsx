import React, { forwardRef } from 'react'

/**
 * TextArea — 多行文本输入框
 *
 * 用法：
 *   <TextArea value={v} onChange={...} rows={4} placeholder="..." />
 */
const TextArea = forwardRef(function TextArea(
  {
    value,
    onChange,
    onKeyDown,
    placeholder,
    rows = 3,
    disabled = false,
    readOnly = false,
    className = '',
    name,
    id,
    spellCheck = false,
    ...rest
  },
  ref,
) {
  return (
    <textarea
      ref={ref}
      value={value}
      onChange={onChange}
      onKeyDown={onKeyDown}
      placeholder={placeholder}
      rows={rows}
      disabled={disabled}
      readOnly={readOnly}
      name={name}
      id={id}
      spellCheck={spellCheck}
      className={`textarea ${className}`}
      {...rest}
    />
  )
})

export default TextArea
