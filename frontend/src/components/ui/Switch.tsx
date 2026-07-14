import { forwardRef } from 'react'
import { clsx } from 'clsx'
import { Switch as ShadcnSwitch } from './shadcn/switch'

export interface SwitchProps {
  label?: string
  checked?: boolean
  defaultChecked?: boolean
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void
  disabled?: boolean
  name?: string
  value?: string
  id?: string
  required?: boolean
  className?: string
  'aria-label'?: string
}

// Adapter: legacy checkbox-style Switch API (onChange with e.target.checked)
// on top of the shadcn (radix) Switch so existing call sites stay unchanged.
export const Switch = forwardRef<HTMLButtonElement, SwitchProps>(
  ({ className, label, onChange, ...props }, ref) => {
    return (
      <label className={clsx('inline-flex cursor-pointer items-center gap-3', className)}>
        <ShadcnSwitch
          ref={ref}
          {...props}
          onCheckedChange={(checked) => {
            onChange?.({ target: { checked } } as React.ChangeEvent<HTMLInputElement>)
          }}
        />
        {label && <span className="text-sm text-foreground">{label}</span>}
      </label>
    )
  }
)

Switch.displayName = 'Switch'
