import type { ReactNode } from 'react'
import { statusTone, titleCaseStatus } from '../../utils/format'

type Props = {
  status: string
  className?: string
}

export function StatusBadge({ status, className = '' }: Props) {
  const tone = statusTone(status)
  return (
    <span className={`badge badge-${tone} ${className}`.trim()} title={status}>
      {titleCaseStatus(status)}
    </span>
  )
}

type ButtonProps = {
  children: ReactNode
  onClick?: () => void
  type?: 'button' | 'submit' | 'reset'
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'md' | 'sm'
  disabled?: boolean
  className?: string
  'aria-label'?: string
}

export function Button({
  children,
  onClick,
  type = 'button',
  variant = 'secondary',
  size = 'md',
  disabled,
  className = '',
  'aria-label': ariaLabel,
}: ButtonProps) {
  const variantClass =
    variant === 'primary'
      ? 'btn-primary'
      : variant === 'danger'
        ? 'btn-danger'
        : variant === 'ghost'
          ? 'btn-ghost'
          : 'btn-secondary'
  const sizeClass = size === 'sm' ? 'btn-sm' : ''
  return (
    <button
      type={type}
      className={`btn ${variantClass} ${sizeClass} ${className}`.trim()}
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
    >
      {children}
    </button>
  )
}

type StateProps = {
  title: string
  message?: string
  action?: ReactNode
  variant?: 'empty' | 'error' | 'loading'
}

export function StatePanel({ title, message, action, variant = 'empty' }: StateProps) {
  return (
    <div className={`state-panel card card-body ${variant === 'error' ? 'error' : ''}`.trim()}>
      {variant === 'loading' ? <div className="spinner" aria-hidden /> : null}
      <h3>{title}</h3>
      {message ? <p>{message}</p> : null}
      {action ? <div style={{ marginTop: '0.85rem' }}>{action}</div> : null}
    </div>
  )
}

export function LoadingBlock({ label = 'Loading…' }: { label?: string }) {
  return <StatePanel title={label} variant="loading" />
}

type ModalProps = {
  open: boolean
  title: string
  children: ReactNode
  onClose: () => void
  actions?: ReactNode
}

export function Modal({ open, title, children, onClose, actions }: ModalProps) {
  if (!open) return null
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="modal-title">{title}</h3>
        <div>{children}</div>
        {actions ? <div className="modal-actions">{actions}</div> : null}
      </div>
    </div>
  )
}

export function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: { id: string; title: string; message?: string; tone: string }[]
  onDismiss: (id: string) => void
}) {
  return (
    <div className="toast-stack" aria-live="polite" aria-relevant="additions">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast ${toast.tone}`} role="status">
          <div className="split" style={{ justifyContent: 'space-between' }}>
            <strong>{toast.title}</strong>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              aria-label="Dismiss notification"
              onClick={() => onDismiss(toast.id)}
            >
              ×
            </button>
          </div>
          {toast.message ? <p>{toast.message}</p> : null}
        </div>
      ))}
    </div>
  )
}
