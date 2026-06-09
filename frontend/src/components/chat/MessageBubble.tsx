import type { ChatMessage, TodoListContent, HITLContent, PlotContent } from '@/types/chat'
import { TodoList } from './TodoList'
import { HITLRequest } from './HITLRequest'

function isTodoListContent(content: unknown): content is TodoListContent {
  return (
    typeof content === 'object' &&
    content !== null &&
    'text' in content &&
    'tasks' in content
  )
}

function isHITLContent(content: unknown): content is HITLContent {
  return (
    typeof content === 'object' &&
    content !== null &&
    'checkpoint' in content &&
    'task_id' in content
  )
}

function isPlotContent(content: unknown): content is PlotContent {
  return (
    typeof content === 'object' &&
    content !== null &&
    'image_base64' in content &&
    'plot_type' in content
  )
}

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
        if (isTodoListContent(message.content)) {
          return <TodoList content={message.content} />
        }
        return null
      case 'hitl_request':
        if (isHITLContent(message.content)) {
          return <HITLRequest checkpoint={message.content.checkpoint} taskId={message.content.task_id} />
        }
        return null
      case 'plot':
        if (isPlotContent(message.content)) {
          return (
            <div className="space-y-2">
              {message.content.title && (
                <div className="text-xs font-medium text-slate-600">{message.content.title}</div>
              )}
              <img
                src={`data:image/png;base64,${message.content.image_base64}`}
                alt={message.content.plot_type}
                className="max-w-full rounded-lg border border-slate-200 shadow-sm"
                style={{ maxHeight: '320px' }}
              />
              {message.content.caption && (
                <div className="text-xs italic text-slate-500">{message.content.caption}</div>
              )}
            </div>
          )
        }
        return null
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
