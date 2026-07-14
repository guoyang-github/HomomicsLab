import { useState } from 'react'
import { clsx } from 'clsx'
import { AnimatePresence, motion } from 'framer-motion'
import { Brain, ChevronDown } from 'lucide-react'
import { useTranslation } from '@/i18n'

interface Props {
  reasoning: string
  /** While true, the header shows a pulsing indicator (streaming in progress). */
  streaming?: boolean
}

const COLLAPSE_TRANSITION = { duration: 0.2, ease: [0.2, 0, 0, 1] as const }

export function ReasoningBlock({ reasoning, streaming = false }: Props) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)

  if (!reasoning.trim()) return null

  return (
    <div className="mb-3 overflow-hidden rounded-lg border border-border/60 bg-muted/30">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-muted-foreground transition-colors hover:bg-muted/50"
      >
        <Brain className="h-3.5 w-3.5 shrink-0" />
        <span className="font-medium">{t('reasoning.title')}</span>
        {streaming && (
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
        )}
        <ChevronDown
          className={clsx(
            'ml-auto h-3.5 w-3.5 shrink-0 transition-transform duration-fast',
            open && 'rotate-180'
          )}
        />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={COLLAPSE_TRANSITION}
            className="overflow-hidden"
          >
            <div className="max-h-64 overflow-y-auto whitespace-pre-wrap border-t border-border/60 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
              {reasoning}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
