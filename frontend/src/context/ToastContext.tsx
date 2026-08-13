import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

export type ToastTone = 'info' | 'success' | 'warning' | 'danger'

export type Toast = {
  id: string
  title: string
  message?: string
  tone: ToastTone
}

type ToastContextValue = {
  toasts: Toast[]
  notify: (input: Omit<Toast, 'id'> & { id?: string }) => void
  dismiss: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const notify = useCallback(
    (input: Omit<Toast, 'id'> & { id?: string }) => {
      const id = input.id || `toast-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      const toast: Toast = {
        id,
        title: input.title,
        message: input.message,
        tone: input.tone,
      }
      setToasts((prev) => [...prev.slice(-4), toast])
      window.setTimeout(() => dismiss(id), 5000)
    },
    [dismiss],
  )

  const value = useMemo(() => ({ toasts, notify, dismiss }), [toasts, notify, dismiss])

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return ctx
}
