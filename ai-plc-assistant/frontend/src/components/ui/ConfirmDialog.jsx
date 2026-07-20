import React, { useEffect, useRef } from 'react'

/**
 * ConfirmDialog — 确认对话框
 *
 * 工业工作台要求"危险按钮具体文案"。
 *
 * 用法：
 *   <ConfirmDialog
 *     title="删除对话"
 *     description="确认删除此对话？此操作不可撤销。"
 *     confirmLabel="确认删除"
 *     variant="danger"
 *     onConfirm={handleDelete}
 *     onClose={handleClose}
 *   />
 */
export default function ConfirmDialog({
  title,
  description,
  confirmLabel = '确认',
  cancelLabel = '取消',
  variant = 'default',
  onConfirm,
  onClose,
  children,
  className = '',
}) {
  const confirmRef = useRef(null)

  useEffect(() => {
    // 打开时自动聚焦确认按钮
    confirmRef.current?.focus()
    // Esc 关闭
    const handler = (e) => { if (e.key === 'Escape') onClose?.() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  const handleConfirm = () => {
    onConfirm?.()
    onClose?.()
  }

  const confirmClass =
    variant === 'danger' ? 'btn btn-danger' :
    variant === 'primary' ? 'btn btn-primary' :
    'btn'

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
    >
      <div
        className={`modal w-[360px] ${className}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <span id="confirm-title">{title}</span>
        </div>
        <div className="modal-body">
          {description && <div className="text-xs text-text-secondary">{description}</div>}
          {children}
        </div>
        <div className="modal-footer">
          <button type="button" onClick={onClose} className="btn">
            {cancelLabel}
          </button>
          <button
            type="button"
            ref={confirmRef}
            onClick={handleConfirm}
            className={confirmClass}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
