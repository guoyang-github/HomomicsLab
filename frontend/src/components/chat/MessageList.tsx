import { useEffect, useRef } from 'react'
import { useChatStore } from '@/stores/chatStore'
import { MessageBubble } from './MessageBubble'
import { EmptyState } from '@/components/ui'
import { Sparkles } from 'lucide-react'

export function MessageList() {
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
          title="开始新的分析对话"
          description="描述您的生物信息分析需求，例如：'帮我完成 PBMC 单细胞数据的标准化与聚类分析'"
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
