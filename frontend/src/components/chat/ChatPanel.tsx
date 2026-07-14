import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useChatStore } from '@/stores/chatStore'
import { useSettingsStore } from '@/stores/settingsStore'
import { useExecutionStore } from '@/stores/executionStore'
import { useTranslation } from '@/i18n'
import { MessageList } from './MessageList'
import { ChatInput } from './ChatInput'
import { ExecutionProgressBar } from './ExecutionProgressBar'
import { CommandPalette } from '@/components/ui/CommandPalette'
import { ExecutionSSEConnector } from '@/components/workspace/ExecutionSSEConnector'
import { ExecutionLogPanel } from '@/components/workspace/ExecutionLogPanel'
import { Badge } from '@/components/ui'

export function ChatPanel() {
  const { t } = useTranslation()
  const [commandOpen, setCommandOpen] = useState(false)
  const isTyping = useChatStore((state) => state.isTyping)
  const openExplorationMode = useSettingsStore((state) => state.openExplorationMode)
  const executionStatus = useExecutionStore((state) => state.status)
  const executionLogCount = useExecutionStore((state) => state.logs.length)
  const showExecutionLogs = executionStatus !== 'idle' || executionLogCount > 0

  return (
    <div className="flex h-full flex-col bg-background">
      <div className="flex h-12 shrink-0 items-center justify-between border-b border-border-faint bg-surface px-4">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-foreground">{t('nav.chat')}</h2>
          {openExplorationMode && (
            <Badge variant="secondary" size="sm">
              {t('chat.openExplorationActive')}
            </Badge>
          )}
        </div>
        {isTyping && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            {t('chat.agentThinking')}
          </div>
        )}
      </div>

      <ExecutionSSEConnector />
      <ExecutionProgressBar />
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
