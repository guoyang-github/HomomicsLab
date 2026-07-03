import { useEffect, useMemo, useRef, useState } from 'react'
import { clsx } from 'clsx'
import { Search, X, Command, MessageSquare, Workflow, FlaskConical, Settings, FileText, FolderOpen, Image } from 'lucide-react'
import { Modal } from './Modal'
import { useTranslation } from '@/i18n'

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
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([])

  useEffect(() => {
    if (open) {
      setQuery('')
      setSelectedIndex(0)
    }
  }, [open])

  const defaultItems: CommandItem[] = useMemo(() => {
    const nav = (path: string) => {
      onNavigate?.(path)
      onClose()
    }
    return [
      { id: 'new-chat', title: t('commandPalette.newChat'), icon: MessageSquare, shortcut: '⌘N', onSelect: () => nav('chat') },
      { id: 'workflow', title: t('commandPalette.openWorkflow'), icon: Workflow, shortcut: '⌘1', onSelect: () => nav('workflow') },
      { id: 'skills', title: t('commandPalette.browseSkills'), icon: FlaskConical, shortcut: '⌘2', onSelect: () => nav('skills') },
      { id: 'reports', title: t('commandPalette.viewReports'), icon: FileText, shortcut: '⌘3', onSelect: () => nav('reports') },
      { id: 'figures', title: t('commandPalette.openFigures'), icon: Image, shortcut: '⌘7', onSelect: () => nav('figures') },
      { id: 'domains', title: t('commandPalette.domainMarketplace'), icon: FolderOpen, shortcut: '⌘4', onSelect: () => nav('domains') },
      { id: 'settings', title: t('commandPalette.openSettings'), icon: Settings, shortcut: '⌘,', onSelect: () => nav('settings') },
    ]
  }, [onNavigate, onClose, t])

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

  const flatItems = useMemo(() => {
    const grouped: Record<string, CommandItem[]> = {}
    filtered.forEach((item) => {
      const section = item.section || 'Commands'
      grouped[section] = grouped[section] || []
      grouped[section].push(item)
    })
    return Object.entries(grouped).flatMap(([, sectionItems]) => sectionItems)
  }, [filtered])

  useEffect(() => {
    // Clamp selection when the filtered list changes.
    if (selectedIndex >= flatItems.length) {
      setSelectedIndex(Math.max(0, flatItems.length - 1))
    }
  }, [flatItems.length, selectedIndex])

  useEffect(() => {
    // Keep the selected item visible.
    itemRefs.current[selectedIndex]?.scrollIntoView({ block: 'nearest' })
  }, [selectedIndex])

  const handleSelect = (item: CommandItem) => {
    item.onSelect()
    onClose()
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (flatItems.length === 0) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev + 1) % flatItems.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev - 1 + flatItems.length) % flatItems.length)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const item = flatItems[selectedIndex]
      if (item) handleSelect(item)
    }
  }

  return (
    <Modal open={open} onClose={onClose} size="xl">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setSelectedIndex(0)
          }}
          onKeyDown={handleKeyDown}
          placeholder={t('commandPalette.placeholder')}
          className="h-12 w-full rounded-lg border border-border bg-card pl-10 pr-10 text-sm outline-none focus-visible:ring-2 focus-visible:ring-primary"
          autoFocus
          aria-autocomplete="list"
          aria-controls="command-palette-listbox"
          aria-activedescendant={flatItems[selectedIndex]?.id}
        />
        <button
          type="button"
          onClick={onClose}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          aria-label={t('common.close')}
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div
        id="command-palette-listbox"
        role="listbox"
        className="mt-2 max-h-[60vh] overflow-y-auto"
      >
        {filtered.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            {t('commandPalette.noResults')}
          </div>
        ) : (
          Object.entries(
            flatItems.reduce<Record<string, CommandItem[]>>((acc, item) => {
              const section = item.section || 'Commands'
              acc[section] = acc[section] || []
              acc[section].push(item)
              return acc
            }, {})
          ).map(([section, sectionItems]) => (
            <div key={section} className="py-2">
              <div className="px-2 py-1 text-xs font-medium text-muted-foreground">{section}</div>
              {sectionItems.map((item) => {
                const Icon = item.icon || Command
                const index = flatItems.findIndex((i) => i.id === item.id)
                const isSelected = index === selectedIndex
                return (
                  <button
                    key={item.id}
                    ref={(el) => {
                      itemRefs.current[index] = el
                    }}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => handleSelect(item)}
                    onMouseEnter={() => setSelectedIndex(index)}
                    className={clsx(
                      'flex w-full items-center gap-3 rounded-md px-2 py-2 text-sm transition-colors',
                      isSelected ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'
                    )}
                  >
                    <Icon className={clsx('h-4 w-4', isSelected ? 'text-primary-foreground' : 'text-muted-foreground')} />
                    <span className="flex-1 text-left">{item.title}</span>
                    {item.shortcut && (
                      <kbd className={clsx('rounded px-1.5 py-0.5 text-[10px]', isSelected ? 'bg-primary-foreground/20 text-primary-foreground' : 'bg-muted text-muted-foreground')}>
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
