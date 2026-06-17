import { useEffect, useRef } from 'react'
import { clsx } from 'clsx'
import { X } from 'lucide-react'
import { Button } from './Button'

export interface ModalProps {
  open: boolean
  onClose: () => void
  title?: string
  description?: string
  children: React.ReactNode
  footer?: React.ReactNode
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full'
}

const sizeClasses = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-2xl',
  full: 'max-w-[90vw]',
}

export function Modal({ open, onClose, title, description, children, footer, size = 'md' }: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    if (open) {
      document.addEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'hidden'
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm animate-fade-in"
      onClick={(e) => e.target === overlayRef.current && onClose()}
    >
      <div
        className={clsx(
          'relative flex max-h-[85vh] w-full flex-col rounded-xl border border-border bg-card text-card-foreground shadow-floating animate-slide-in',
          sizeClasses[size]
        )}
        role="dialog"
        aria-modal="true"
      >
        {(title || description) && (
          <div className="flex shrink-0 items-start justify-between border-b border-border p-5">
            <div className="min-w-0 pr-4">
              {title && <h2 className="truncate text-lg font-semibold">{title}</h2>}
              {description && <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{description}</p>}
            </div>
            <Button variant="ghost" size="icon" onClick={onClose} className="shrink-0">
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}
        <div className="flex-1 overflow-y-auto p-5">{children}</div>
        {footer && <div className="flex shrink-0 items-center justify-end gap-2 border-t border-border p-5">{footer}</div>}
      </div>
    </div>
  )
}
