import { useState, useMemo } from 'react'
import { clsx } from 'clsx'
import {
  Search,
  Bell,
  Moon,
  Sun,
  Monitor,
  PanelLeft,
  FolderKanban,
} from 'lucide-react'
import { Button } from '@/components/ui'
import { useTheme } from '@/hooks/useTheme'
import { useProjectStore } from '@/stores/projectStore'
import { useTranslation } from '@/i18n'

export interface TopBarProps {
  onOpenCommandPalette: () => void
  collapsed: boolean
  onToggleSidebar: () => void
}

export function TopBar({ onOpenCommandPalette, collapsed, onToggleSidebar }: TopBarProps) {
  const { t } = useTranslation()
  const { theme, setTheme } = useTheme()
  const [notifications] = useState(0)
  const projects = useProjectStore((state) => state.projects)
  const currentProjectId = useProjectStore((state) => state.currentProjectId)
  const currentProjectName = useMemo(() => {
    if (currentProjectId === 'default') return t('topbar.defaultProject')
    const project = projects.find((p) => p.id === currentProjectId)
    return project?.name || currentProjectId
  }, [projects, currentProjectId, t])

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-card px-4">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={onToggleSidebar} title={collapsed ? t('topbar.expandSidebar') : t('topbar.collapseSidebar')}>
          <PanelLeft className="h-5 w-5" />
        </Button>
        <button
          onClick={onOpenCommandPalette}
          className={clsx(
            'hidden items-center gap-2 rounded-lg border border-border bg-muted/50 px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted sm:flex',
            'w-64'
          )}
        >
          <Search className="h-4 w-4" />
          <span className="flex-1 text-left">{t('topbar.searchCommands')}</span>
          <kbd className="rounded bg-card px-1.5 py-0.5 text-[10px]">⌘K</kbd>
        </button>
      </div>

      <div className="hidden items-center gap-2 text-sm text-muted-foreground sm:flex">
        <FolderKanban className="h-4 w-4" />
        <span className="font-medium text-foreground">{currentProjectName}</span>
      </div>

      <div className="flex items-center gap-1">
        <Button variant="ghost" size="icon" className="relative" title={t('topbar.notifications')}>
          <Bell className="h-5 w-5" />
          {notifications > 0 && (
            <span className="absolute right-1.5 top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-error text-[10px] text-white">
              {notifications}
            </span>
          )}
        </Button>

        <div className="flex items-center rounded-lg border border-border p-0.5">
          <Button
            variant={theme === 'light' ? 'secondary' : 'ghost'}
            size="icon"
            onClick={() => setTheme('light')}
            title={t('topbar.light')}
          >
            <Sun className="h-4 w-4" />
          </Button>
          <Button
            variant={theme === 'system' ? 'secondary' : 'ghost'}
            size="icon"
            onClick={() => setTheme('system')}
            title={t('topbar.system')}
          >
            <Monitor className="h-4 w-4" />
          </Button>
          <Button
            variant={theme === 'dark' ? 'secondary' : 'ghost'}
            size="icon"
            onClick={() => setTheme('dark')}
            title={t('topbar.dark')}
          >
            <Moon className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </header>
  )
}
