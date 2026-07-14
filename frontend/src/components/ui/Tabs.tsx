import { clsx } from 'clsx'
import {
  Tabs as ShadcnTabs,
  TabsList as ShadcnTabsList,
  TabsTrigger as ShadcnTabsTrigger,
  TabsContent as ShadcnTabsContent,
} from './shadcn/tabs'

export interface TabsProps {
  defaultValue: string
  value?: string
  onValueChange?: (value: string) => void
  children: React.ReactNode
  className?: string
}

// Adapter: legacy Tabs API on top of the shadcn (radix) Tabs primitives.
export function Tabs({ className, ...props }: TabsProps) {
  return <ShadcnTabs className={clsx('flex flex-col', className)} {...props} />
}

export type TabsListProps = React.ComponentProps<typeof ShadcnTabsList>

export function TabsList({ className, ...props }: TabsListProps) {
  return <ShadcnTabsList className={clsx('gap-1', className)} {...props} />
}

export type TabsTriggerProps = React.ComponentProps<typeof ShadcnTabsTrigger>

export function TabsTrigger(props: TabsTriggerProps) {
  return <ShadcnTabsTrigger {...props} />
}

export type TabsContentProps = React.ComponentProps<typeof ShadcnTabsContent>

export function TabsContent({ className, ...props }: TabsContentProps) {
  return <ShadcnTabsContent className={clsx('animate-fade-in', className)} {...props} />
}
