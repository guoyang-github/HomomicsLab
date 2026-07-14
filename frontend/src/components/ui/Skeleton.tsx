import { clsx } from 'clsx'
import { Skeleton as ShadcnSkeleton } from './shadcn/skeleton'

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  circle?: boolean
}

// Adapter: keeps the legacy `circle` prop on top of the shadcn skeleton.
export function Skeleton({ className, circle, ...props }: SkeletonProps) {
  return <ShadcnSkeleton className={clsx(circle ? 'rounded-full' : 'rounded-md', className)} {...props} />
}
