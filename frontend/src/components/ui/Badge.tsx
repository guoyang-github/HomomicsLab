import { clsx } from 'clsx'
import { Badge as ShadcnBadge } from './shadcn/badge'

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'secondary' | 'outline' | 'success' | 'warning' | 'error' | 'info'
  size?: 'sm' | 'md'
}

// Status variants the shadcn badge does not ship with. They are rendered on
// top of the shadcn "outline" variant with the legacy soft-tint classes.
const statusVariantClasses: Record<string, string> = {
  default: 'border-transparent bg-primary/10 text-primary dark:bg-primary/20',
  success: 'border-transparent bg-success/10 text-success dark:bg-success/20',
  warning: 'border-transparent bg-warning/10 text-warning dark:bg-warning/20',
  error: 'border-transparent bg-error/10 text-error dark:bg-error/20',
  info: 'border-transparent bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
}

export function Badge({ className, variant = 'default', size = 'sm', children, ...props }: BadgeProps) {
  const statusClasses = statusVariantClasses[variant]

  return (
    <ShadcnBadge
      variant={variant === 'secondary' ? 'secondary' : 'outline'}
      className={clsx(
        'rounded-full font-medium',
        variant === 'outline' && 'border-border text-muted-foreground',
        statusClasses,
        size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs',
        className
      )}
      {...props}
    >
      {children}
    </ShadcnBadge>
  )
}
