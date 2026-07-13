import { useState } from 'react'
import { clsx } from 'clsx'
import { MessageSquare, Loader2 } from 'lucide-react'
import { useChatStore } from '@/stores/chatStore'
import { useSettingsStore } from '@/stores/settingsStore'
import { useTranslation } from '@/i18n'
import { MessageList } from './MessageList'
import { ChatInput } from './ChatInput'
import { SessionList } from './SessionList'
import { CommandPalette } from '@/components/ui/CommandPalette'
import { ExecutionSSEConnector } from '@/components/workspace/ExecutionSSEConnector'
import { Badge } from '@/components/ui'

export function ChatPanel() {
  const { t } = useTranslation()
  const [showSessions, setShowSessions] = useState(true)
  const [commandOpen, setCommandOpen] = useState(false)
  const isTyping = useChatStore((state) => state.isTyping)
  const openExplorationMode = useSettingsStore((state) => state.openExplorationMode)

  return (
    <div className="flex h-full overflow-hidden">
      {showSessions && (
        <div className="w-60 shrink-0">
          <SessionList />
        </div>
      )}

      <div className="flex flex-1 flex-col bg-background">
        <div className="flex h-14 items-center justify-between border-b border-border bg-card px-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSessions((s) => !s)}
              className={clsx(
                'rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
                showSessions && 'text-primary'
              )}
              title={showSessions ? t('chat.toggleSidebarHide') : t('chat.toggleSidebarShow')}
            >
              <MessageSquare className="h-5 w-5" />
            </button>
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
        <MessageList />
        <ChatInput onOpenCommandPalette={() => setCommandOpen(true)} />

        <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} />
      </div>
    </div>
  )
}
