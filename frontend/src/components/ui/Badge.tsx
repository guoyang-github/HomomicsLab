import { clsx } from 'clsx'

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'secondary' | 'outline' | 'success' | 'warning' | 'error' | 'info'
  size?: 'sm' | 'md'
}

export function Badge({ className, variant = 'default', size = 'sm', children, ...props }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full font-medium transition-colors',
        {
          'bg-primary/10 text-primary dark:bg-primary/20': variant === 'default',
          'bg-secondary text-secondary-foreground': variant === 'secondary',
          'border border-border text-muted-foreground': variant === 'outline',
          'bg-success/10 text-success dark:bg-success/20': variant === 'success',
          'bg-warning/10 text-warning dark:bg-warning/20': variant === 'warning',
          'bg-error/10 text-error dark:bg-error/20': variant === 'error',
          'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300': variant === 'info',
        },
        {
          'px-2 py-0.5 text-[10px]': size === 'sm',
          'px-2.5 py-1 text-xs': size === 'md',
        },
        className
      )}
      {...props}
    >
      {children}
    </span>
  )
}
