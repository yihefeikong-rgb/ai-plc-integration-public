import React, { useRef } from 'react'
import useEscClose from '../../hooks/useEscClose'
import useFocusTrap from '../../hooks/useFocusTrap'
import { DANGER_BUTTON_LABELS } from '../../platform/safetyLevels'

/**
 * ConfirmDialog — 确认对话框（F-015 焦点锁定 + F-017 危险按钮具体文案）
 *
 * 用法：
 *   <ConfirmDialog
 *     title="删除对话"
 *     description="确认删除此对话？此操作不可撤销。"
 *     confirmLabel="确认删除对话"
 *     variant="danger"
 *     onConfirm={handleDelete}
 *     onClose={handleClose}
 *   />
 *
 * 或用 dangerAction 自动取具体文案：
 *   <ConfirmDialog
 *     title="停止 CPU"
 *     dangerAction="STOP_CPU"  // 自动取 DANGER_BUTTON_LABELS.STOP_CPU
 *     variant="danger"
 *     onConfirm={handleStop}
 *     onClose={handleClose}
 *   />
 */
export default function ConfirmDialog({
  title,
  description,
  confirmLabel,
  dangerAction,  // 'STOP_CPU' | 'DOWNLOAD_TO_PLC' | 'OVERWRITE_BLOCK' | 'WRITE_VARIABLE'
  cancelLabel = '取消',
  variant = 'default',
  onConfirm,
  onClose,
  children,
  className = '',
}) {
  const containerRef = useRef(null)
  const confirmRef = useRef(null)

  // F-015：焦点锁定（Tab 在弹窗内循环 + 卸载恢复焦点）
  useFocusTrap(containerRef, true)
  // F-016：Esc 关闭
  useEscClose(onClose)

  // F-017：dangerAction 自动取具体文案
  const resolvedConfirmLabel = confirmLabel ||
    (dangerAction && DANGER_BUTTON_LABELS[dangerAction]) ||
    '确认'

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
        ref={containerRef}
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
            {resolvedConfirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
