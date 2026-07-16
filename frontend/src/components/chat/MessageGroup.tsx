import { motion } from 'framer-motion'
import { clsx } from 'clsx'
import { Bot, AlertCircle, User, Copy, Check, RotateCcw, ThumbsUp, ThumbsDown } from 'lucide-react'
import { useState } from 'react'
import { Avatar, AvatarFallback } from '@/components/ui/shadcn/avatar'
import { MessageBubble } from './MessageBubble'
import { ExecutionResult } from './ExecutionResult'
import { useTranslation } from '@/i18n'
import { chatApi } from '@/services/api'
import { toastSuccess } from '@/stores/toastStore'
import type { ChatMessage, TodoListContent } from '@/types/chat'

const MESSAGE_ENTER_TRANSITION = { duration: 0.2, ease: [0.2, 0, 0, 1] as const }

const OUTPUT_MESSAGE_TYPES = new Set(['artifact', 'file_reference', 'plot', 'plot_data'])

function isOutputMessage(message: ChatMessage): boolean {
  return OUTPUT_MESSAGE_TYPES.has(message.type)
}

function isTodoListMessage(message: ChatMessage): boolean {
  return message.type === 'todo_list'
}

interface MessageGroupProps {
  messages: ChatMessage[]
  onRegenerate?: () => void
  isLastGroup?: boolean
}

export function MessageGroup({ messages, onRegenerate, isLastGroup }: MessageGroupProps) {
  const { t } = useTranslation()
  const first = messages[0]
  const isUser = first.sender === 'user'
  const isSystem = first.sender === 'system'
  const [copied, setCopied] = useState(false)
  const [feedback, setFeedback] = useState<'positive' | 'negative' | null>(null)

  const RoleIcon = isUser ? User : isSystem ? AlertCircle : Bot
  const roleLabel = isUser
    ? t('message.you')
    : isSystem
    ? t('message.system')
    : t('message.agent')

  const showActions = !isUser && !isSystem

  // A single user/system turn is rendered as-is. Agent turns are split into
  // main content (text, plans, etc.) and an output section (files / artifacts /
  // todo_list outputs) that is pinned to the bottom of the reply.
  let mainMessages = messages
  let outputMessages: ChatMessage[] = []
  let todoListMessages: ChatMessage[] = []

  if (!isUser && !isSystem) {
    mainMessages = messages.filter((m) => !isOutputMessage(m) && !isTodoListMessage(m))
    outputMessages = messages.filter((m) => isOutputMessage(m))
    todoListMessages = messages.filter((m) => isTodoListMessage(m))
  }

  const handleCopy = async () => {
    const text = messages
      .map((m) => (typeof m.content === 'string' ? m.content : JSON.stringify(m.content, null, 2)))
      .join('\n\n')
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleFeedback = async (rating: 'positive' | 'negative') => {
    setFeedback(rating)
    try {
      const lastAgentMessage = [...messages].reverse().find((m) => m.sender === 'agent')
      if (lastAgentMessage) {
        await chatApi.submitFeedback({ message_id: lastAgentMessage.id, rating })
      }
      toastSuccess(t('common.saved'))
    } catch {
      // Best-effort
    }
  }

  const hasOutputs = outputMessages.length > 0 || todoListMessages.length > 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={MESSAGE_ENTER_TRANSITION}
      className="group flex gap-3 sm:gap-4"
    >
      <Avatar
        className={clsx(
          'mt-0.5 h-8 w-8 shrink-0 border-2',
          isUser
            ? 'border-primary/20'
            : isSystem
            ? 'border-warning/30'
            : 'border-accent/30'
        )}
      >
        <AvatarFallback
          className={clsx(
            isUser
              ? 'bg-primary/10 text-primary'
              : isSystem
              ? 'bg-warning/10 text-warning'
              : 'bg-accent/10 text-accent'
          )}
        >
          <RoleIcon className="h-4 w-4" />
        </AvatarFallback>
      </Avatar>

      <div className="min-w-0 flex-1">
        <div className="mb-1.5 flex items-center gap-2 text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">{roleLabel}</span>
          <span>{new Date(first.timestamp).toLocaleTimeString()}</span>
          {showActions && (
            <div className="ml-auto flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
              <button
                onClick={handleCopy}
                className="rounded p-1 hover:bg-surface-2"
                title={t('message.copy')}
              >
                {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
              {isLastGroup && onRegenerate && (
                <button onClick={onRegenerate} className="rounded p-1 hover:bg-surface-2" title={t('message.regenerate')}>
                  <RotateCcw className="h-3.5 w-3.5" />
                </button>
              )}
              <button
                onClick={() => handleFeedback('positive')}
                className={clsx(
                  'rounded p-1 hover:bg-surface-2',
                  feedback === 'positive' && 'text-success'
                )}
                title={t('message.useful')}
              >
                <ThumbsUp className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => handleFeedback('negative')}
                className={clsx(
                  'rounded p-1 hover:bg-surface-2',
                  feedback === 'negative' && 'text-error'
                )}
                title={t('message.notUseful')}
              >
                <ThumbsDown className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>

        <div className="space-y-6">
          {mainMessages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              hideHeader
              hideRelatedFiles
              onRegenerate={undefined}
            />
          ))}

          {hasOutputs && (
            <div className="space-y-4 rounded-xl border border-border-faint bg-surface/50 p-4">
              <p className="text-xs font-medium text-muted-foreground">{t('common.output')}</p>
              <div className="space-y-6">
                {outputMessages.map((message) => (
                  <MessageBubble
                    key={message.id}
                    message={message}
                    hideHeader
                    hideRelatedFiles
                    onRegenerate={undefined}
                  />
                ))}
                {todoListMessages.map((message) => {
                  const content = message.content as unknown as TodoListContent
                  return (
                    <ExecutionResult
                      key={message.id}
                      content={content}
                      mode="outputs-only"
                    />
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}
