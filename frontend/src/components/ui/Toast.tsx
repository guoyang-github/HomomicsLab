import { useEffect } from 'react'
import { clsx } from 'clsx'
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react'

export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface Toast {
  id: string
  type: ToastType
  title?: string
  message: string
  duration?: number
}

export interface ToastItemProps extends Toast {
  onRemove: (id: string) => void
}

const icons: Record<ToastType, React.ElementType> = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}

const styles: Record<ToastType, string> = {
  success: 'bg-success/10 text-success border-success/20',
  error: 'bg-error/10 text-error border-error/20',
  warning: 'bg-warning/10 text-warning border-warning/20',
  info: 'bg-primary/10 text-primary border-primary/20',
}

export function ToastItem({ id, type, title, message, duration = 5000, onRemove }: ToastItemProps) {
  const Icon = icons[type]

  useEffect(() => {
    if (duration <= 0) return
    const timer = setTimeout(() => onRemove(id), duration)
    return () => clearTimeout(timer)
  }, [id, duration, onRemove])

  return (
    <div
      className={clsx(
        'pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-lg border p-4 shadow-floating animate-slide-in',
        styles[type]
      )}
    >
      <Icon className="mt-0.5 h-5 w-5 shrink-0" />
      <div className="flex-1">
        {title && <p className="font-medium">{title}</p>}
        <p className={clsx('text-sm', title && 'mt-1')}>{message}</p>
      </div>
      <button onClick={() => onRemove(id)} className="shrink-0 rounded p-1 hover:bg-black/5">
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}

export interface ToastContainerProps {
  toasts: Toast[]
  onRemove: (id: string) => void
}

export function ToastContainer({ toasts, onRemove }: ToastContainerProps) {
  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} {...toast} onRemove={onRemove} />
      ))}
    </div>
  )
}
