import { useEffect, useRef } from 'react'
import { toast as sonnerToast } from 'sonner'
import { Toaster } from './shadcn/sonner'

export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface Toast {
  id: string
  type: ToastType
  title?: string
  message: string
  duration?: number
}

export interface ToastContainerProps {
  toasts: Toast[]
  onRemove: (id: string) => void
}

// Adapter: the toast store stays the source of truth (call sites unchanged),
// but rendering is delegated to sonner. New store entries are drained into
// sonner toasts; removals dismiss them again.
export function ToastContainer({ toasts, onRemove }: ToastContainerProps) {
  const shownRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    const shown = shownRef.current
    const currentIds = new Set(toasts.map((t) => t.id))

    for (const toast of toasts) {
      if (shown.has(toast.id)) continue
      shown.add(toast.id)
      const options = {
        id: toast.id,
        description: toast.title ? toast.message : undefined,
        duration: toast.duration === undefined ? 5000 : toast.duration <= 0 ? Infinity : toast.duration,
        onDismiss: () => onRemove(toast.id),
        onAutoClose: () => onRemove(toast.id),
      }
      sonnerToast[toast.type](toast.title ?? toast.message, options)
    }

    for (const id of Array.from(shown)) {
      if (!currentIds.has(id)) {
        sonnerToast.dismiss(id)
        shown.delete(id)
      }
    }
  }, [toasts, onRemove])

  return <Toaster position="bottom-right" richColors closeButton />
}
