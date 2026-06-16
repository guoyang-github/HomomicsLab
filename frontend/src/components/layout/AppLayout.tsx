import { useState, useEffect, useCallback } from 'react'
import { clsx } from 'clsx'
import { Sidebar } from './Sidebar'
import type { NavItem } from './Sidebar'
import { TopBar } from './TopBar'
import { CommandPalette } from '@/components/ui/CommandPalette'
import { ToastContainer } from '@/components/ui/Toast'
import { useToastStore } from '@/stores/toastStore'

interface AppLayoutProps {
  activeItem: NavItem
  onNavigate: (item: NavItem) => void
  children: React.ReactNode
}

export function AppLayout({ activeItem, onNavigate, children }: AppLayoutProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [commandOpen, setCommandOpen] = useState(false)
  const toasts = useToastStore((state) => state.toasts)
  const removeToast = useToastStore((state) => state.removeToast)

  const toggleSidebar = () => setCollapsed((c) => !c)

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const isMeta = e.metaKey || e.ctrlKey

      if (isMeta && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setCommandOpen((open) => !open)
      }

      if (isMeta) {
        const navMap: Record<string, NavItem> = {
          '1': 'chat',
          '2': 'workflow',
          '3': 'reports',
          '4': 'skills',
          '5': 'domains',
        }
        if (navMap[e.key]) {
          e.preventDefault()
          onNavigate(navMap[e.key])
        }
        if (e.key === ',') {
          e.preventDefault()
          onNavigate('settings')
        }
      }

      if (e.key === 'Escape') {
        setCommandOpen(false)
      }
    },
    [onNavigate]
  )

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      <Sidebar
        activeItem={activeItem}
        onNavigate={onNavigate}
        collapsed={collapsed}
        onToggleCollapse={toggleSidebar}
      />

      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar
          onOpenCommandPalette={() => setCommandOpen(true)}
          collapsed={collapsed}
          onToggleSidebar={toggleSidebar}
        />
        <main className={clsx('flex-1 overflow-hidden bg-background')}>{children}</main>
      </div>

      <CommandPalette
        open={commandOpen}
        onClose={() => setCommandOpen(false)}
        onNavigate={(path) => onNavigate(path as NavItem)}
      />

      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </div>
  )
}
