import { forwardRef } from 'react'
import { clsx } from 'clsx'

export interface SwitchProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string
}

export const Switch = forwardRef<HTMLInputElement, SwitchProps>(
  ({ className, label, ...props }, ref) => {
    return (
      <label className={clsx('inline-flex cursor-pointer items-center gap-3', className)}>
        <div className="relative inline-flex h-5 w-9 items-center">
          <input
            ref={ref}
            type="checkbox"
            className="peer sr-only"
            {...props}
          />
          <span className="absolute inset-0 rounded-full bg-muted transition-colors peer-checked:bg-primary peer-disabled:opacity-50" />
          <span className="absolute left-0.5 h-4 w-4 rounded-full bg-white transition-transform peer-checked:translate-x-4" />
        </div>
        {label && <span className="text-sm text-foreground">{label}</span>}
      </label>
    )
  }
)

Switch.displayName = 'Switch'
