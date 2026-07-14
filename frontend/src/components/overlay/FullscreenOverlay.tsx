import { X } from 'lucide-react'
import { clsx } from 'clsx'

interface FullscreenOverlayProps {
  title: string
  children: React.ReactNode
  onClose: () => void
}

export function FullscreenOverlay({ title, children, onClose }: FullscreenOverlayProps) {
  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-background">
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-card px-4">
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
        <button
          type="button"
          onClick={onClose}
          className={clsx(
            'inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors',
            'hover:bg-muted hover:text-foreground'
          )}
          aria-label="Close"
        >
          <X className="h-5 w-5" />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
    </div>
  )
}
