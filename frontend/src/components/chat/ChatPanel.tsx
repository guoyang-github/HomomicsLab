import { useState } from 'react'
import { clsx } from 'clsx'
import { MessageSquare, Loader2, FileText, Workflow, Image, Folder } from 'lucide-react'
import { useChatStore } from '@/stores/chatStore'
import { useSettingsStore } from '@/stores/settingsStore'
import { useExecutionStore } from '@/stores/executionStore'
import { useOverlayStore } from '@/stores/overlayStore'
import { useTranslation } from '@/i18n'
import { MessageList } from './MessageList'
import { ChatInput } from './ChatInput'
import { SessionList } from './SessionList'
import { CommandPalette } from '@/components/ui/CommandPalette'
import { ExecutionSSEConnector } from '@/components/workspace/ExecutionSSEConnector'
import { ExecutionLogPanel } from '@/components/workspace/ExecutionLogPanel'
import { Badge, Tooltip } from '@/components/ui'

export function ChatPanel() {
  const { t } = useTranslation()
  const [showSessions, setShowSessions] = useState(true)
  const [commandOpen, setCommandOpen] = useState(false)
  const isTyping = useChatStore((state) => state.isTyping)
  const openExplorationMode = useSettingsStore((state) => state.openExplorationMode)
  const executionStatus = useExecutionStore((state) => state.status)
  const executionLogCount = useExecutionStore((state) => state.logs.length)
  const showExecutionLogs = executionStatus !== 'idle' || executionLogCount > 0

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
          <div className="flex items-center gap-2">
            <ChatOverlayToolbar />
            {isTyping && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                {t('chat.agentThinking')}
              </div>
            )}
          </div>
        </div>

        <ExecutionSSEConnector />
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
    </div>
  )
}

function ChatOverlayToolbar() {
  const { t } = useTranslation()
  const openReport = useOverlayStore((state) => state.openReport)
  const openWorkflow = useOverlayStore((state) => state.openWorkflow)
  const openFigure = useOverlayStore((state) => state.openFigure)

  const items = [
    { id: 'reports', icon: FileText, label: t('chat.openReports'), onClick: () => openReport() },
    { id: 'workflow', icon: Workflow, label: t('chat.openWorkflow'), onClick: () => openWorkflow() },
    { id: 'figures', icon: Image, label: t('chat.openFigures'), onClick: () => openFigure() },
    { id: 'files', icon: Folder, label: t('chat.openFiles'), onClick: () => (window.location.hash = '#/files') },
  ]

  return (
    <div className="flex items-center gap-0.5">
      {items.map((item) => {
        const Icon = item.icon
        return (
          <Tooltip key={item.id} content={item.label}>
            <button
              type="button"
              onClick={item.onClick}
              className={clsx(
                'inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors',
                'hover:bg-muted hover:text-foreground'
              )}
              aria-label={item.label}
            >
              <Icon className="h-4 w-4" />
            </button>
          </Tooltip>
        )
      })}
    </div>
  )
}
