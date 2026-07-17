import { useState } from 'react'
import { useActiveExecutionJob } from '@/hooks/useActiveExecutionJob'
import { MessageList } from './MessageList'
import { ChatInput } from './ChatInput'
import { TodoChecklist } from './TodoChecklist'
import { CommandPalette } from '@/components/ui/CommandPalette'
import { ExecutionSSEConnector } from '@/components/workspace/ExecutionSSEConnector'
import { ExecutionLogPanel } from '@/components/workspace/ExecutionLogPanel'

export function ChatPanel() {
  const [commandOpen, setCommandOpen] = useState(false)
  // The active job is tracked per session, so it is always scoped to the
  // session currently on screen — no cross-session gating needed here.
  const { job } = useActiveExecutionJob()
  const showExecutionLogs = job?.status === 'running'

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
