import { MessageList } from './MessageList'
import { ChatInput } from './ChatInput'

export function ChatPanel() {
  return (
    <div className="flex h-full flex-col border-r border-slate-200 bg-slate-50">
      <div className="border-b border-slate-200 bg-white px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-800">对话</h2>
      </div>
      <MessageList />
      <ChatInput />
    </div>
  )
}
