import { useState } from 'react'
import { clsx } from 'clsx'
import { Maximize2, Send, Wand2 } from 'lucide-react'
import { PlotChart } from '@/components/shared/PlotChart'
import { useChatStore } from '@/stores/chatStore'
import { useTranslation } from '@/i18n'
import { useOverlayStore } from '@/stores/overlayStore'
import type { PlotContent, PlotDataContent } from '@/types/chat'

interface FigureCardProps {
  content: PlotContent | PlotDataContent
  type: 'plot' | 'plot_data'
}

export function FigureCard({ content, type }: FigureCardProps) {
  const { t } = useTranslation()
  const sendMessage = useChatStore((state) => state.sendMessage)
  const openFigure = useOverlayStore((state) => state.openFigure)
  const [editText, setEditText] = useState('')
  const [isSending, setIsSending] = useState(false)

  const title = content.title || content.plot_type

  const handleEditSubmit = async () => {
    const trimmed = editText.trim()
    if (!trimmed || isSending) return
    setIsSending(true)
    try {
      await sendMessage(trimmed)
      setEditText('')
    } finally {
      setIsSending(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleEditSubmit()
    }
  }

  return (
    <div className="w-full space-y-2 rounded-xl border border-border-faint bg-surface p-1 shadow-sm">
      <div className="flex items-center justify-between px-2 pt-1">
        <div className="flex items-center gap-2 text-xs font-medium text-foreground">
          <Wand2 className="h-3.5 w-3.5 text-accent" />
          <span className="truncate" title={title}>
            {title}
          </span>
        </div>
        <button
          type="button"
          onClick={() =>
            openFigure({
              plot:
                type === 'plot'
                  ? { type: 'plot' as const, content: content as PlotContent }
                  : { type: 'plot_data' as const, content: content as PlotDataContent },
            })
          }
          className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground"
          title={t('message.fullscreenPlot')}
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="relative overflow-hidden rounded-lg border border-border-faint">
        {type === 'plot' ? (
          <img
            src={`data:image/png;base64,${(content as PlotContent).image_base64}`}
            alt={content.plot_type}
            className="max-w-full rounded-lg bg-white object-contain"
            style={{ maxHeight: '360px' }}
          />
        ) : (
          <PlotChart
            request={{
              plot_type: content.plot_type as any,
              data: (content as PlotDataContent).data,
              title: content.title,
              width: 700,
              height: 420,
            }}
            className="w-full bg-white"
          />
        )}
      </div>

      {content.caption && (
        <div className="px-2 text-xs italic text-muted-foreground">{content.caption}</div>
      )}

      <div className="flex items-center gap-1 px-2 pb-1.5">
        <input
          type="text"
          value={editText}
          onChange={(e) => setEditText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t('figureCard.editPlaceholder')}
          className={clsx(
            'h-8 flex-1 rounded-lg border border-border-faint bg-surface-2 px-3 text-xs',
            'text-foreground placeholder:text-muted-foreground',
            'focus-visible:border-accent/50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent/30'
          )}
        />
        <button
          type="button"
          onClick={handleEditSubmit}
          disabled={isSending || !editText.trim()}
          className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
          title={t('figureCard.editSubmit')}
        >
          {isSending ? (
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-accent-foreground/30 border-t-accent-foreground" />
          ) : (
            <Send className="h-3.5 w-3.5" />
          )}
        </button>
      </div>
    </div>
  )
}
