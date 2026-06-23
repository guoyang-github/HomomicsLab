import { clsx } from 'clsx'
import {
  MessageSquare,
  Workflow,
  FlaskConical,
  FolderOpen,
  Folder,
  FileText,
  Settings,
  Command,
  Image,
  type LucideIcon,
} from 'lucide-react'
import { useTranslation } from '@/i18n'

export type NavItem =
  | 'chat'
  | 'workflow'
  | 'reports'
  | 'files'
  | 'figures'
  | 'skills'
  | 'domains'
  | 'settings'

interface SidebarItem {
  id: NavItem
  labelKey: string
  icon: LucideIcon
  shortcut?: string
}

const navItems: SidebarItem[] = [
  { id: 'chat', labelKey: 'nav.chat', icon: MessageSquare, shortcut: '⌘1' },
  { id: 'workflow', labelKey: 'nav.workflow', icon: Workflow, shortcut: '⌘2' },
  { id: 'reports', labelKey: 'nav.reports', icon: FileText, shortcut: '⌘3' },
  { id: 'files', labelKey: 'nav.files', icon: Folder, shortcut: '⌘4' },
  { id: 'figures', labelKey: 'nav.figures', icon: Image, shortcut: '⌘7' },
  { id: 'skills', labelKey: 'nav.skills', icon: FlaskConical, shortcut: '⌘5' },
  { id: 'domains', labelKey: 'nav.domains', icon: FolderOpen, shortcut: '⌘6' },
  { id: 'settings', labelKey: 'nav.settings', icon: Settings, shortcut: '⌘,' },
]

interface SidebarProps {
  activeItem: NavItem
  onNavigate: (item: NavItem) => void
  collapsed?: boolean
  onToggleCollapse?: () => void
}

export function Sidebar({ activeItem, onNavigate, collapsed = false }: SidebarProps) {
  const { t } = useTranslation()
  return (
    <aside
      className={clsx(
        'flex h-full flex-col border-r border-border bg-card transition-all duration-200',
        collapsed ? 'w-16' : 'w-60'
      )}
    >
      <div className="flex h-14 items-center gap-2 border-b border-border px-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-white">
          <Command className="h-5 w-5" />
        </div>
        {!collapsed && (
          <div className="flex flex-col overflow-hidden">
            <span className="truncate text-sm font-bold text-foreground">HomomicsLab</span>
            <span className="truncate text-[10px] text-muted-foreground">Bioinfo Agent</span>
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-1 p-3">
        {navItems.map((item) => {
          const Icon = item.icon
          const label = t(item.labelKey)
          const isActive = activeItem === item.id
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={clsx(
                'group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
              title={collapsed ? label : undefined}
            >
              <Icon className={clsx('h-5 w-5 shrink-0', isActive && 'text-primary')} />
              {!collapsed && <span className="flex-1 text-left">{label}</span>}
              {!collapsed && item.shortcut && (
                <kbd className="hidden rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground group-hover:inline-block">
                  {item.shortcut}
                </kbd>
              )}
            </button>
          )
        })}
      </nav>

      <div className="border-t border-border p-3">
        <div
          className={clsx(
            'rounded-lg bg-muted/50 px-3 py-2 text-xs text-muted-foreground',
            collapsed && 'px-2 text-center'
          )}
        >
          {collapsed ? 'v0.4' : 'HomomicsLab v0.4.2'}
        </div>
      </div>
    </aside>
  )
}
