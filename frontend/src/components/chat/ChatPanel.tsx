import { useState } from 'react'
import { useExecutionStore } from '@/stores/executionStore'
import { MessageList } from './MessageList'
import { ChatInput } from './ChatInput'
import { TodoChecklist } from './TodoChecklist'
import { CommandPalette } from '@/components/ui/CommandPalette'
import { ExecutionSSEConnector } from '@/components/workspace/ExecutionSSEConnector'
import { ExecutionLogPanel } from '@/components/workspace/ExecutionLogPanel'

export function ChatPanel() {
  const [commandOpen, setCommandOpen] = useState(false)
  const executionStatus = useExecutionStore((state) => state.status)
  const showExecutionLogs = executionStatus === 'running'

  return (
    <div className="flex h-full flex-col bg-background">
      <ExecutionSSEConnector />
      <MessageList />
      <TodoChecklist />
      {showExecutionLogs && (
        <div className="px-4 pb-2">
          <div className="mx-auto w-full max-w-[780px]">
            <ExecutionLogPanel compact />
          </div>
        </div>
      )}
      <ChatInput onOpenCommandPalette={() => setCommandOpen(true)} />

      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} />
    </div>
  )
}
