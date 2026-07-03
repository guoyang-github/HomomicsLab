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

const FOCUSABLE_SELECTOR = [
  'button:not([disabled])',
  'a[href]',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"]):not([disabled])',
].join(', ')

export function Modal({ open, onClose, title, description, children, footer, size = 'md' }: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const previousActiveElementRef = useRef<Element | null>(null)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
        return
      }

      if (e.key !== 'Tab' || !containerRef.current) return

      const focusable = Array.from(containerRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
      if (focusable.length === 0) return

      const first = focusable[0]
      const last = focusable[focusable.length - 1]

      if (e.shiftKey) {
        if (document.activeElement === first || !containerRef.current.contains(document.activeElement as Node)) {
          e.preventDefault()
          last.focus()
        }
      } else {
        if (document.activeElement === last || !containerRef.current.contains(document.activeElement as Node)) {
          e.preventDefault()
          first.focus()
        }
      }
    }

    if (open) {
      previousActiveElementRef.current = document.activeElement
      document.addEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'hidden'

      // Focus the first focusable element when the modal opens.
      const timer = setTimeout(() => {
        const focusable = containerRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
        if (focusable && focusable.length > 0) {
          focusable[0].focus()
        } else {
          containerRef.current?.focus()
        }
      }, 0)

      return () => {
        document.removeEventListener('keydown', handleKeyDown)
        document.body.style.overflow = ''
        clearTimeout(timer)
      }
    }
  }, [open, onClose])

  useEffect(() => {
    return () => {
      // Restore focus to the element that triggered the modal when it unmounts.
      if (previousActiveElementRef.current instanceof HTMLElement) {
        previousActiveElementRef.current.focus()
      }
    }
  }, [])

  if (!open) return null

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm animate-fade-in"
      onClick={(e) => e.target === overlayRef.current && onClose()}
    >
      <div
        ref={containerRef}
        tabIndex={-1}
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
            <Button variant="ghost" size="icon" onClick={onClose} className="shrink-0" aria-label={title ? `Close ${title}` : 'Close'}>
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
