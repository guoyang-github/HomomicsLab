import { useState } from 'react'
import { clsx } from 'clsx'
import { motion } from 'framer-motion'
import {
  AlertCircle,
  Bot,
  Copy,
  Check,
  RotateCcw,
  ThumbsUp,
  ThumbsDown,
  FileText,
  Eye,
  Quote,
  User,
} from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/shadcn/avatar'
import { MarkdownRenderer } from '@/components/shared/MarkdownRenderer'
import { ExecutionResult } from './ExecutionResult'
import { ExecutionPlan } from './ExecutionPlan'
import { HITLRequest } from './HITLRequest'
import { PlanApproval } from './PlanApproval'
import { DebateRequest } from './DebateRequest'
import { ResultPreview, type ResultPreviewContent } from './ResultPreview'
import { FollowUpSuggestions } from './FollowUpSuggestions'
import { ReasoningBlock } from './ReasoningBlock'
import { FigureCard } from './FigureCard'
import { useTranslation } from '@/i18n'
import { chatApi, fileApi } from '@/services/api'
import { toastSuccess } from '@/stores/toastStore'
import { useProjectStore } from '@/stores/projectStore'
import { useChatStore } from '@/stores/chatStore'
import type {
  ChatMessage,
  TodoListContent,
  ExecutionPlanContent,
  HITLContent,
  PlotContent,
  PlotDataContent,
  PlanRequestContent,
  DebateRequestContent,
  FollowUpContent,
} from '@/types/chat'

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

function isExecutionPlanContent(content: unknown): content is ExecutionPlanContent {
  return (
    typeof content === 'object' &&
    content !== null &&
    'plan_id' in content &&
    'tasks' in content
  )
}

function isPlanRequestContent(content: unknown): content is PlanRequestContent {
  return (
    typeof content === 'object' &&
    content !== null &&
    'plan_id' in content &&
    'plan' in content
  )
}

function isDebateRequestContent(content: unknown): content is DebateRequestContent {
  return (
    typeof content === 'object' &&
    content !== null &&
    'debate_id' in content &&
    'options' in content
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

function isPlotDataContent(content: unknown): content is PlotDataContent {
  return (
    typeof content === 'object' &&
    content !== null &&
    'data' in content &&
    'plot_type' in content &&
    !('image_base64' in content)
  )
}

function isResultPreviewContent(content: unknown): content is ResultPreviewContent {
  return (
    typeof content === 'object' &&
    content !== null &&
    'tool_calls' in content &&
    Array.isArray((content as Record<string, unknown>).tool_calls)
  )
}

function isFollowUpContent(content: unknown): content is FollowUpContent {
  return (
    typeof content === 'object' &&
    content !== null &&
    'suggestions' in content &&
    Array.isArray((content as Record<string, unknown>).suggestions)
  )
}

const MESSAGE_ENTER_TRANSITION = { duration: 0.2, ease: [0.2, 0, 0, 1] as const }

interface Props {
  message: ChatMessage
  onRegenerate?: () => void
  hideHeader?: boolean
  hideRelatedFiles?: boolean
}

export function MessageBubble({ message, onRegenerate, hideHeader, hideRelatedFiles }: Props) {
  const { t } = useTranslation()
  const isUser = message.sender === 'user'
  const isSystem = message.sender === 'system'
  const currentProjectId = useProjectStore((state) => state.currentProjectId)
  const setDraftInput = useChatStore((state) => state.setDraftInput)
  const [copied, setCopied] = useState(false)
  const [feedback, setFeedback] = useState<'positive' | 'negative' | null>(null)

  // Avoid rendering empty/whitespace-only text bubbles (e.g. stale LLM output).
  if (
    message.type === 'text' &&
    typeof message.content === 'string' &&
    !message.content.trim()
  ) {
    return null
  }

  const reasoning =
    !isUser && typeof message.metadata?.reasoning === 'string'
      ? message.metadata.reasoning
      : !isUser && typeof message.metadata?.thinking === 'string'
      ? message.metadata.thinking
      : null

  const handleCopy = async () => {
    const text = typeof message.content === 'string' ? message.content : JSON.stringify(message.content, null, 2)
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleFeedback = async (rating: 'positive' | 'negative') => {
    setFeedback(rating)
    try {
      await chatApi.submitFeedback({ message_id: message.id, rating })
      toastSuccess(t('common.saved'))
    } catch {
      // Best-effort; keep local state even if network fails.
    }
  }

  const renderContent = () => {
    if (typeof message.content === 'string') {
      // Strip the backend file-reference appendix from user-visible text;
      // the resolved file is already shown as an attachment chip below.
      const cleaned = isUser
        ? message.content.replace(
            /\n?\n---\n\nReferenced context:\n\n<file[^>]*>.*?<\/file>\s*$/s,
            ''
          )
        : message.content
      return <MarkdownRenderer content={cleaned} />
    }

    switch (message.type) {
      case 'todo_list':
        if (isTodoListContent(message.content)) {
          return <ExecutionResult content={message.content} />
        }
        return null
      case 'execution_plan':
        if (isExecutionPlanContent(message.content)) {
          return <ExecutionPlan content={message.content} />
        }
        return null
      case 'hitl_request':
        if (isHITLContent(message.content)) {
          return (
            <HITLRequest
              checkpoint={message.content.checkpoint}
              taskId={message.content.task_id}
            />
          )
        }
        return null
      case 'plan_request':
        if (isPlanRequestContent(message.content)) {
          return <PlanApproval content={message.content} />
        }
        return null
      case 'debate_request':
        if (isDebateRequestContent(message.content)) {
          return <DebateRequest content={message.content} />
        }
        return null
      case 'plot':
        if (isPlotContent(message.content)) {
          return <FigureCard content={message.content} type="plot" />
        }
        return null
      case 'plot_data':
        if (isPlotDataContent(message.content)) {
          return <FigureCard content={message.content} type="plot_data" />
        }
        return null
      case 'result_preview':
      case 'tool_call':
        if (isResultPreviewContent(message.content)) {
          return <ResultPreview content={message.content} />
        }
        return null
      case 'follow_up':
        if (isFollowUpContent(message.content)) {
          return <FollowUpSuggestions suggestions={message.content.suggestions} />
        }
        return null
      case 'error':
        return (
          <div className="rounded-lg border border-error/20 bg-error/10 p-3 text-sm text-error">
            {String(message.content)}
          </div>
        )
      default:
        return (
          <pre className="overflow-x-auto rounded-lg bg-muted p-3 text-xs">
            {JSON.stringify(message.content, null, 2)}
          </pre>
        )
    }
  }

  const RoleIcon = isUser ? User : isSystem ? AlertCircle : Bot
  const roleLabel = isUser
    ? t('message.you')
    : isSystem
    ? t('message.system')
    : t('message.agent')
  const showActions =
    !isUser &&
    message.type !== 'hitl_request' &&
    message.type !== 'plan_request' &&
    message.type !== 'debate_request' &&
    message.type !== 'execution_plan'

  const contentBody = (
    <>
      {reasoning && <ReasoningBlock reasoning={reasoning} />}

      {isUser ? (
        <div className="inline-block max-w-full rounded-2xl bg-surface px-4 py-2.5 text-[15px] leading-relaxed">
          {renderContent()}
        </div>
      ) : (
        <div className="text-[15px] leading-relaxed">{renderContent()}</div>
      )}

      {!hideRelatedFiles && message.related_files && message.related_files.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {message.related_files.map((path) => {
            const name = path.split('/').pop() || path
            return (
              <div
                key={path}
                className="flex items-center gap-1.5 rounded-md border border-border-faint bg-surface px-2 py-1 text-xs"
              >
                <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="max-w-[160px] truncate" title={path}>
                  {name}
                </span>
                <button
                  onClick={() => window.open(fileApi.previewUrl(currentProjectId, path), '_blank')}
                  className="rounded p-0.5 hover:bg-muted"
                  title={t('files.preview')}
                >
                  <Eye className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => {
                    setDraftInput(`@file:${path}`)
                    toastSuccess(t('files.referenceSuccess'))
                  }}
                  className="rounded p-0.5 hover:bg-muted"
                  title={t('files.reference')}
                >
                  <Quote className="h-3.5 w-3.5" />
                </button>
              </div>
            )
          })}
        </div>
      )}
    </>
  )

  if (hideHeader) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={MESSAGE_ENTER_TRANSITION}
        className="w-full"
      >
        {contentBody}
      </motion.div>
    )
  }

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
          <span>{new Date(message.timestamp).toLocaleTimeString()}</span>
          {showActions && (
            <div className="ml-auto flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
              <button
                onClick={handleCopy}
                className="rounded p-1 hover:bg-surface-2"
                title={t('message.copy')}
              >
                {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
              {onRegenerate && (
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

        {contentBody}
      </div>
    </motion.div>
  )
}
