import { useEffect, useRef } from 'react'
import { useChatStore } from '@/stores/chatStore'
import { MessageBubble } from './MessageBubble'
import { EmptyState } from '@/components/ui'
import { Sparkles } from 'lucide-react'
import { useTranslation } from '@/i18n'

export function MessageList() {
  const { t } = useTranslation()
  const messages = useChatStore((state) => state.messages)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center overflow-y-auto p-4">
        <EmptyState
          icon={Sparkles}
          title={t('chat.emptyTitle')}
          description={t('chat.emptyDesc')}
        />
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="mx-auto max-w-3xl space-y-2">
        {messages.map((message, index) => (
          <MessageBubble
            key={message.id}
            message={message}
            onRegenerate={
              message.sender === 'agent' && index === messages.length - 1
                ? () => {
                    // TODO: implement regenerate
                  }
                : undefined
            }
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
