import { useState } from 'react'
import { clsx } from 'clsx'
import { ChevronDown } from 'lucide-react'

export interface AccordionItem {
  id: string
  title: React.ReactNode
  content: React.ReactNode
}

export interface AccordionProps {
  items: AccordionItem[]
  defaultOpen?: string[]
  allowMultiple?: boolean
  className?: string
}

export function Accordion({ items, defaultOpen = [], allowMultiple = true, className }: AccordionProps) {
  const [openItems, setOpenItems] = useState<Set<string>>(new Set(defaultOpen))

  const toggle = (id: string) => {
    setOpenItems((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        if (!allowMultiple) next.clear()
        next.add(id)
      }
      return next
    })
  }

  return (
    <div className={clsx('divide-y divide-border rounded-lg border border-border', className)}>
      {items.map((item) => {
        const isOpen = openItems.has(item.id)
        return (
          <div key={item.id} className="bg-card">
            <button
              onClick={() => toggle(item.id)}
              className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium hover:bg-muted/50"
            >
              {item.title}
              <ChevronDown className={clsx('h-4 w-4 transition-transform', isOpen && 'rotate-180')} />
            </button>
            {isOpen && <div className="px-4 pb-3 text-sm text-muted-foreground">{item.content}</div>}
          </div>
        )
      })}
    </div>
  )
}
