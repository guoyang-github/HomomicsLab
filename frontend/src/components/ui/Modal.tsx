import { clsx } from 'clsx'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './shadcn/dialog'

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

// Adapter: legacy Modal API on top of the shadcn (radix) Dialog. Escape,
// overlay click, focus trap/restore and scroll lock are handled by radix.
export function Modal({ open, onClose, title, description, children, footer, size = 'md' }: ModalProps) {
  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className={clsx('flex max-h-[85vh] flex-col gap-0 p-0', sizeClasses[size])}>
        {title || description ? (
          <DialogHeader className="shrink-0 border-b border-border p-5 text-left">
            {title ? (
              <DialogTitle className="truncate pr-6 text-lg">{title}</DialogTitle>
            ) : (
              <DialogTitle className="sr-only">Dialog</DialogTitle>
            )}
            {description ? (
              <DialogDescription className="line-clamp-2">{description}</DialogDescription>
            ) : (
              <DialogDescription className="sr-only">{title ?? 'Dialog'}</DialogDescription>
            )}
          </DialogHeader>
        ) : (
          <>
            <DialogTitle className="sr-only">Dialog</DialogTitle>
            <DialogDescription className="sr-only">Dialog</DialogDescription>
          </>
        )}
        <div className="flex-1 overflow-y-auto p-5">{children}</div>
        {footer && (
          <DialogFooter className="flex-row items-center justify-end gap-2 border-t border-border p-5 sm:space-x-0">
            {footer}
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  )
}
