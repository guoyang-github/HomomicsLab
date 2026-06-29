import { Lightbulb } from 'lucide-react'
import { useTranslation } from '@/i18n'
import { useChatStore } from '@/stores/chatStore'

interface Props {
  suggestions: string[]
}

export function FollowUpSuggestions({ suggestions }: Props) {
  const { t } = useTranslation()
  const sendMessage = useChatStore((state) => state.sendMessage)

  return (
    <div className="mt-2 space-y-2">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Lightbulb className="h-3.5 w-3.5" />
        <span>{t('followUp.title')}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {suggestions.map((text, idx) => (
          <button
            key={idx}
            onClick={() => sendMessage(text)}
            className="max-w-full rounded-full border border-border bg-background px-3 py-1.5 text-left text-xs text-foreground transition-colors hover:bg-primary/5 hover:text-primary"
            title={text}
          >
            <span className="line-clamp-1">{text}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
