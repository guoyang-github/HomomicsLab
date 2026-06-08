import type { ChatMessage } from '@/types/chat'

interface Props {
  message: ChatMessage
}

export function MessageBubble({ message }: Props) {
  const isUser = message.sender === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2 ${
          isUser
            ? 'bg-primary text-white'
            : 'bg-white border border-slate-200 text-slate-800'
        }`}
      >
        <div className="text-xs opacity-75 mb-1">
          {isUser ? 'You' : 'Agent'} • {new Date(message.timestamp).toLocaleTimeString()}
        </div>
        <div className="text-sm">
          {typeof message.content === 'string'
            ? message.content
            : JSON.stringify(message.content, null, 2)}
        </div>
      </div>
    </div>
  )
}
