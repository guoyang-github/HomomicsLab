import { useState } from 'react'
import { useExecutionStore } from '@/stores/executionStore'
import { useChatStore } from '@/stores/chatStore'
import { MessageList } from './MessageList'
import { ChatInput } from './ChatInput'
import { TodoChecklist } from './TodoChecklist'
import { CommandPalette } from '@/components/ui/CommandPalette'
import { ExecutionSSEConnector } from '@/components/workspace/ExecutionSSEConnector'
import { ExecutionLogPanel } from '@/components/workspace/ExecutionLogPanel'

export function ChatPanel() {
  const [commandOpen, setCommandOpen] = useState(false)
  const executionStatus = useExecutionStore((state) => state.status)
  const jobSessionId = useExecutionStore((state) => state.jobSessionId)
  const currentSessionId = useChatStore((state) => state.currentSessionId)
  const isJobForCurrentSession = !jobSessionId || jobSessionId === currentSessionId
  const showExecutionLogs = executionStatus === 'running' && isJobForCurrentSession

  return (
    <div className="relative flex h-full flex-col bg-background">
      <ExecutionSSEConnector />
      <TodoChecklist />
      <MessageList />
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
