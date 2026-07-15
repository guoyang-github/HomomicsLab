import { useState, useMemo, useRef, useEffect } from 'react'
import {
  Search,
  Bell,
  Moon,
  Sun,
  Monitor,
  Download,
  User,
  LogOut,
} from 'lucide-react'
import { Button } from '@/components/ui'
import { useTheme } from '@/hooks/useTheme'
import { useProjectStore } from '@/stores/projectStore'
import { useToastStore } from '@/stores/toastStore'
import { projectApi } from '@/services/api'
import { useTranslation } from '@/i18n'

export interface TopBarProps {
  onOpenCommandPalette: () => void
}

export function TopBar({ onOpenCommandPalette }: TopBarProps) {
  const { t } = useTranslation()
  const { theme, setTheme } = useTheme()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const projects = useProjectStore((state) => state.projects)
  const currentProjectId = useProjectStore((state) => state.currentProjectId)
  const addToast = useToastStore((state) => state.addToast)
  const notifications = 0
  const menuRef = useRef<HTMLDivElement>(null)

  const currentProjectName = useMemo(() => {
    if (currentProjectId === 'default') return t('topbar.defaultProject')
    const project = projects.find((p) => p.id === currentProjectId)
    return project?.name || currentProjectId
  }, [currentProjectId, projects, t])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    if (userMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [userMenuOpen])

  const handleExportROcrate = async () => {
    if (currentProjectId === 'default') {
      addToast({ type: 'error', message: t('topbar.exportROcrateFailed') })
      return
    }
    try {
      const response = await projectApi.exportROCrate(currentProjectId)
      const blob = new Blob([response.data], { type: 'application/zip' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${currentProjectId}_rocrate.zip`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch {
      addToast({ type: 'error', message: t('topbar.exportROcrateFailed') })
    }
    setUserMenuOpen(false)
  }

  return (
    <header className="flex h-10 shrink-0 items-center justify-between border-b border-border-faint bg-surface px-3">
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={onOpenCommandPalette}
          title={`${t('topbar.searchCommands')} (⌘K)`}
          aria-label={t('topbar.searchCommands')}
          className="h-8 w-8"
        >
          <Search className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex items-center gap-1">
        <div className="flex items-center rounded-lg border border-border-faint p-0.5">
          <Button
            variant={theme === 'light' ? 'secondary' : 'ghost'}
            size="icon"
            onClick={() => setTheme('light')}
            title={t('topbar.light')}
            className="h-7 w-7"
          >
            <Sun className="h-4 w-4" />
          </Button>
          <Button
            variant={theme === 'system' ? 'secondary' : 'ghost'}
            size="icon"
            onClick={() => setTheme('system')}
            title={t('topbar.system')}
            className="h-7 w-7"
          >
            <Monitor className="h-4 w-4" />
          </Button>
          <Button
            variant={theme === 'dark' ? 'secondary' : 'ghost'}
            size="icon"
            onClick={() => setTheme('dark')}
            title={t('topbar.dark')}
            className="h-7 w-7"
          >
            <Moon className="h-4 w-4" />
          </Button>
        </div>

        <div className="relative" ref={menuRef}>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => setUserMenuOpen((open) => !open)}
            title={currentProjectName}
          >
            <User className="h-5 w-5" />
          </Button>

          {userMenuOpen && (
            <div className="absolute right-0 top-full z-50 mt-1 w-56 rounded-lg border border-border-faint bg-surface p-1 shadow-lg">
              <div className="border-b border-border-faint px-3 py-2">
                <p className="text-xs font-medium text-foreground">{currentProjectName}</p>
                <p className="text-[10px] text-muted-foreground">{t('common.project')}</p>
              </div>
              <button
                type="button"
                onClick={handleExportROcrate}
                disabled={currentProjectId === 'default'}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-xs text-foreground transition-colors hover:bg-surface-2 disabled:opacity-50"
              >
                <Download className="h-3.5 w-3.5" />
                {t('topbar.exportROcrate')}
              </button>
              <button
                type="button"
                disabled
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-xs text-muted-foreground disabled:opacity-50"
              >
                <Bell className="h-3.5 w-3.5" />
                {t('topbar.notifications')}
                {notifications > 0 && (
                  <span className="ml-auto flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-error px-1 text-[10px] text-white">
                    {notifications}
                  </span>
                )}
              </button>
              <button
                type="button"
                disabled
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-xs text-muted-foreground disabled:opacity-50"
              >
                <LogOut className="h-3.5 w-3.5" />
                {t('common.logout') || 'Sign out'}
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
