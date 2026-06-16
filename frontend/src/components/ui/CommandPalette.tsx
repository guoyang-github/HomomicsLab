import { useEffect, useMemo, useState } from 'react'
import { clsx } from 'clsx'
import { Search, X, Command, MessageSquare, Workflow, FlaskConical, Settings, FileText, FolderOpen } from 'lucide-react'
import { Modal } from './Modal'

export interface CommandItem {
  id: string
  title: string
  shortcut?: string
  icon?: React.ElementType
  section?: string
  onSelect: () => void
}

export interface CommandPaletteProps {
  open: boolean
  onClose: () => void
  items?: CommandItem[]
  onNavigate?: (path: string) => void
}

export function CommandPalette({ open, onClose, items = [], onNavigate }: CommandPaletteProps) {
  const [query, setQuery] = useState('')

  useEffect(() => {
    if (open) setQuery('')
  }, [open])

  const defaultItems: CommandItem[] = useMemo(() => {
    const nav = (path: string) => {
      onNavigate?.(path)
      onClose()
    }
    return [
      { id: 'new-chat', title: '新建会话', icon: MessageSquare, shortcut: '⌘N', onSelect: () => nav('chat') },
      { id: 'workflow', title: '打开工作流', icon: Workflow, shortcut: '⌘1', onSelect: () => nav('workflow') },
      { id: 'skills', title: '浏览 Skills', icon: FlaskConical, shortcut: '⌘2', onSelect: () => nav('skills') },
      { id: 'reports', title: '查看报告', icon: FileText, shortcut: '⌘3', onSelect: () => nav('reports') },
      { id: 'domains', title: 'Domain 市场', icon: FolderOpen, shortcut: '⌘4', onSelect: () => nav('domains') },
      { id: 'settings', title: '打开设置', icon: Settings, shortcut: '⌘,', onSelect: () => nav('settings') },
    ]
  }, [onNavigate, onClose])

  const allItems = useMemo(() => [...defaultItems, ...items], [defaultItems, items])

  const filtered = useMemo(() => {
    if (!query.trim()) return allItems
    const q = query.toLowerCase()
    return allItems.filter(
      (item) =>
        item.title.toLowerCase().includes(q) ||
        item.section?.toLowerCase().includes(q)
    )
  }, [allItems, query])

  const sections = useMemo(() => {
    const grouped: Record<string, CommandItem[]> = {}
    filtered.forEach((item) => {
      const section = item.section || 'Commands'
      grouped[section] = grouped[section] || []
      grouped[section].push(item)
    })
    return grouped
  }, [filtered])

  const handleSelect = (item: CommandItem) => {
    item.onSelect()
    onClose()
  }

  return (
    <Modal open={open} onClose={onClose} size="xl">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜索命令或跳转..."
          className="h-12 w-full rounded-lg border border-border bg-card pl-10 pr-10 text-sm outline-none focus-visible:ring-2 focus-visible:ring-primary"
          autoFocus
        />
        <button onClick={onClose} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="mt-2 max-h-[60vh] overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            未找到匹配命令
          </div>
        ) : (
          Object.entries(sections).map(([section, sectionItems]) => (
            <div key={section} className="py-2">
              <div className="px-2 py-1 text-xs font-medium text-muted-foreground">{section}</div>
              {sectionItems.map((item) => {
                const Icon = item.icon || Command
                return (
                  <button
                    key={item.id}
                    onClick={() => handleSelect(item)}
                    className={clsx(
                      'flex w-full items-center gap-3 rounded-md px-2 py-2 text-sm transition-colors hover:bg-muted'
                    )}
                  >
                    <Icon className="h-4 w-4 text-muted-foreground" />
                    <span className="flex-1 text-left">{item.title}</span>
                    {item.shortcut && (
                      <kbd className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                        {item.shortcut}
                      </kbd>
                    )}
                  </button>
                )
              })}
            </div>
          ))
        )}
      </div>
    </Modal>
  )
}
