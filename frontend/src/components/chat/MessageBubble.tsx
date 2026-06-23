import { useState } from 'react'
import { clsx } from 'clsx'
import { Copy, Check, RotateCcw, ThumbsUp, ThumbsDown } from 'lucide-react'
import { MarkdownRenderer } from '@/components/shared/MarkdownRenderer'
import { TodoList } from './TodoList'
import { ExecutionPlan } from './ExecutionPlan'
import { HITLRequest } from './HITLRequest'
import { PlanApproval } from './PlanApproval'
import { DebateRequest } from './DebateRequest'
import { PlotChart } from '../shared/PlotChart'
import { useTranslation } from '@/i18n'
import type {
  ChatMessage,
  TodoListContent,
  ExecutionPlanContent,
  HITLContent,
  PlotContent,
  PlotDataContent,
  PlanRequestContent,
  DebateRequestContent,
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

interface Props {
  message: ChatMessage
  onRegenerate?: () => void
}

export function MessageBubble({ message, onRegenerate }: Props) {
  const { t } = useTranslation()
  const isUser = message.sender === 'user'
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    const text = typeof message.content === 'string' ? message.content : JSON.stringify(message.content, null, 2)
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const renderContent = () => {
    if (typeof message.content === 'string') {
      return <MarkdownRenderer content={message.content} />
    }

    switch (message.type) {
      case 'todo_list':
        if (isTodoListContent(message.content)) {
          return <TodoList content={message.content} />
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
          return (
            <div className="space-y-2">
              {message.content.title && (
                <div className="text-xs font-medium text-slate-600 dark:text-slate-300">
                  {message.content.title}
                </div>
              )}
              <img
                src={`data:image/png;base64,${message.content.image_base64}`}
                alt={message.content.plot_type}
                className="max-w-full rounded-lg border border-border shadow-card"
                style={{ maxHeight: '320px' }}
              />
              {message.content.caption && (
                <div className="text-xs italic text-muted-foreground">{message.content.caption}</div>
              )}
            </div>
          )
        }
        return null
      case 'plot_data':
        if (isPlotDataContent(message.content)) {
          return (
            <div className="w-full space-y-2">
              {message.content.title && (
                <div className="text-xs font-medium text-slate-600 dark:text-slate-300">
                  {message.content.title}
                </div>
              )}
              <PlotChart
                request={{
                  plot_type: message.content.plot_type as any,
                  data: message.content.data,
                  title: message.content.title,
                  width: 700,
                  height: 450,
                }}
                className="w-full rounded-lg border border-border"
              />
              {message.content.caption && (
                <div className="text-xs italic text-muted-foreground">{message.content.caption}</div>
              )}
            </div>
          )
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

  return (
    <div className={clsx('group mb-6 flex', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={clsx(
          'relative max-w-[92%] rounded-2xl px-5 py-4 shadow-card transition-shadow hover:shadow-soft sm:max-w-[85%]',
          isUser
            ? 'bg-primary text-white'
            : 'border border-border bg-card text-card-foreground'
        )}
      >
        <div
          className={clsx(
            'mb-2 flex items-center justify-between gap-4 text-xs',
            isUser ? 'text-primary-100' : 'text-muted-foreground'
          )}
        >
          <div className="flex items-center gap-2">
            <span className={clsx('font-semibold', isUser ? 'text-white' : 'text-foreground')}>
              {isUser ? 'You' : 'Homomics Agent'}
            </span>
            <span>•</span>
            <span>{new Date(message.timestamp).toLocaleTimeString()}</span>
          </div>
          {!isUser && message.type !== 'hitl_request' && message.type !== 'plan_request' && message.type !== 'debate_request' && message.type !== 'execution_plan' && (
            <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
              <button
                onClick={handleCopy}
                className="rounded p-1 hover:bg-muted"
                title={t('message.copy')}
              >
                {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
              {onRegenerate && (
                <button onClick={onRegenerate} className="rounded p-1 hover:bg-muted" title={t('message.regenerate')}>
                  <RotateCcw className="h-3.5 w-3.5" />
                </button>
              )}
              <button className="rounded p-1 hover:bg-muted" title={t('message.useful')}>
                <ThumbsUp className="h-3.5 w-3.5" />
              </button>
              <button className="rounded p-1 hover:bg-muted" title={t('message.notUseful')}>
                <ThumbsDown className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>

        <div className={clsx(isUser && 'prose-invert')}>{renderContent()}</div>
      </div>
    </div>
  )
}
