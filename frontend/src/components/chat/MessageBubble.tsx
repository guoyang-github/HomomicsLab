import type { ChatMessage, TodoListContent, HITLContent } from '@/types/chat'
import { TodoList } from './TodoList'
import { HITLRequest } from './HITLRequest'

interface Props {
  message: ChatMessage
}

export function MessageBubble({ message }: Props) {
  const isUser = message.sender === 'user'

  const renderContent = () => {
    if (typeof message.content === 'string') {
      return <p className="text-sm">{message.content}</p>
    }

    switch (message.type) {
      case 'todo_list':
        return <TodoList content={(message.content as unknown) as TodoListContent} />
      case 'hitl_request': {
        const hitl = (message.content as unknown) as HITLContent
        return <HITLRequest checkpoint={hitl.checkpoint} taskId={hitl.task_id} />
      }
      case 'error':
        return <p className="text-sm text-error">{String(message.content)}</p>
      default:
        return <pre className="text-xs">{JSON.stringify(message.content, null, 2)}</pre>
    }
  }

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[90%] rounded-lg px-4 py-3 ${
          isUser
            ? 'bg-primary text-white'
            : 'bg-white border border-slate-200 text-slate-800'
        }`}
      >
        <div className="text-xs opacity-75 mb-1">
          {isUser ? 'You' : 'Agent'} • {new Date(message.timestamp).toLocaleTimeString()}
        </div>
        {renderContent()}
      </div>
    </div>
  )
}
