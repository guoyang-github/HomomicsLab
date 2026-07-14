import { clsx } from 'clsx'
import { useEffect, useState } from 'react'
import {
  MessageSquare,
  FlaskConical,
  FolderOpen,
  Folder,
  Settings,
  Command,
  Plug,
  PanelLeft,
  type LucideIcon,
} from 'lucide-react'
import { useTranslation } from '@/i18n'
import { healthApi } from '@/sdk'
import { SidebarSessions } from './SidebarSessions'

export type NavItem = 'chat' | 'files' | 'skills' | 'domains' | 'mcp' | 'settings'

interface SidebarItem {
  id: NavItem
  labelKey: string
  icon: LucideIcon
  shortcut?: string
}

const navItems: SidebarItem[] = [
  { id: 'chat', labelKey: 'nav.chat', icon: MessageSquare, shortcut: '⌘1' },
  { id: 'files', labelKey: 'nav.files', icon: Folder, shortcut: '⌘2' },
  { id: 'skills', labelKey: 'nav.skills', icon: FlaskConical, shortcut: '⌘3' },
  { id: 'domains', labelKey: 'nav.domains', icon: FolderOpen, shortcut: '⌘4' },
  { id: 'mcp', labelKey: 'nav.mcp', icon: Plug, shortcut: '⌘5' },
  { id: 'settings', labelKey: 'nav.settings', icon: Settings, shortcut: '⌘6' },
]

interface SidebarProps {
  activeItem: NavItem
  onNavigate: (item: NavItem) => void
  collapsed?: boolean
  onToggleCollapse?: () => void
}

export function Sidebar({ activeItem, onNavigate, collapsed = false, onToggleCollapse }: SidebarProps) {
  const { t } = useTranslation()
  const [version, setVersion] = useState<string>('')
  const [llmConfigured, setLlmConfigured] = useState<boolean | null>(null)
  const [llmModel, setLlmModel] = useState<string | null>(null)

  useEffect(() => {
    const fetchHealth = () => {
      healthApi
        .getLive()
        .then((res) => {
          const data = res.data
          if (data?.version) {
            setVersion(data.version)
          }
          if (typeof data?.llm_configured === 'boolean') {
            setLlmConfigured(data.llm_configured)
          }
          if (data?.llm_model) {
            setLlmModel(data.llm_model)
          }
        })
        .catch(() => {
          // ignore; keep empty fallback
        })
    }

    fetchHealth()
    const interval = setInterval(fetchHealth, 10_000)
    return () => clearInterval(interval)
  }, [])

  const versionLabel = version ? `v${version}` : 'v0.1'
  const llmTooltip = llmConfigured
    ? `LLM connected: ${llmModel ?? 'unknown'}`
    : 'LLM not configured — answers use rule-based fallback and web search.'

  return (
    <aside
      className={clsx(
        'flex h-full shrink-0 flex-col border-r border-border-faint bg-surface transition-all duration-200',
        collapsed ? 'w-16' : 'w-60'
      )}
    >
      <div className="flex h-14 shrink-0 items-center gap-2 border-b border-border-faint px-3">
        <div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
          <Command className="h-4 w-4" />
          {collapsed && (
            <span
              className={clsx(
                'absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border-2 border-surface shadow-sm',
                llmConfigured === true && 'bg-green-500',
                llmConfigured === false && 'animate-pulse bg-red-500',
                llmConfigured === null && 'bg-muted-foreground/50'
              )}
              title={llmTooltip}
            />
          )}
        </div>
        {!collapsed && (
          <div className="flex flex-1 flex-col overflow-hidden">
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-bold text-foreground">HomomicsLab</span>
              <span
                className={clsx(
                  'h-2.5 w-2.5 shrink-0 rounded-full shadow-sm',
                  llmConfigured === true && 'bg-green-500',
                  llmConfigured === false && 'animate-pulse bg-red-500',
                  llmConfigured === null && 'bg-muted-foreground/50'
                )}
                title={llmTooltip}
              />
            </div>
            <span className="truncate text-[10px] text-muted-foreground">Bioinfo Agent</span>
          </div>
        )}
        <button
          type="button"
          onClick={onToggleCollapse}
          className={clsx(
            'rounded p-1 text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground',
            collapsed && 'ml-auto'
          )}
          title={collapsed ? t('topbar.expandSidebar') : t('topbar.collapseSidebar')}
        >
          <PanelLeft className={clsx('h-4 w-4', collapsed && 'rotate-180')} />
        </button>
      </div>

      <nav className="shrink-0 space-y-0.5 p-2">
        {navItems.map((item) => {
          const Icon = item.icon
          const label = t(item.labelKey)
          const isActive = activeItem === item.id
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={clsx(
                'group flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-[13px] font-medium transition-colors',
                isActive
                  ? 'bg-surface-2 text-accent'
                  : 'text-muted-foreground hover:bg-surface-2/60 hover:text-foreground'
              )}
              title={collapsed ? label : undefined}
            >
              <Icon className={clsx('h-4 w-4 shrink-0', isActive && 'text-accent')} />
              {!collapsed && <span className="flex-1 text-left">{label}</span>}
              {!collapsed && item.shortcut && (
                <kbd className="hidden rounded bg-surface-2 px-1.5 py-0.5 text-[10px] text-muted-foreground group-hover:inline-block">
                  {item.shortcut}
                </kbd>
              )}
            </button>
          )
        })}
      </nav>

      <SidebarSessions collapsed={collapsed} />

      {!collapsed && (
        <div className="shrink-0 border-t border-border-faint p-2">
          <div className="rounded-lg bg-surface-2/60 px-2.5 py-1.5 text-[10px] text-muted-foreground">
            HomomicsLab {versionLabel}
          </div>
        </div>
      )}
    </aside>
  )
}
