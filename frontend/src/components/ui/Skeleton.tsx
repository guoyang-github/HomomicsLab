import { clsx } from 'clsx'

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  circle?: boolean
}

export function Skeleton({ className, circle, ...props }: SkeletonProps) {
  return (
    <div
      className={clsx(
        'animate-pulse bg-muted',
        circle ? 'rounded-full' : 'rounded-md',
        className
      )}
      {...props}
    />
  )
}
