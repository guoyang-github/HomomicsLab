import { useEffect, useRef, useState } from 'react'
import { useChatStore } from '@/stores/chatStore'
import { useTaskStore } from '@/stores/taskStore'
import { usePlanStore } from '@/stores/planStore'
import { useExecutionStore } from '@/stores/executionStore'
import { MessageBubble } from './MessageBubble'
import { EmptyState } from '@/components/ui'
import { Sparkles } from 'lucide-react'
import { useTranslation } from '@/i18n'
import { chatApi } from '@/services/api'
import { toastError } from '@/stores/toastStore'
import type { PlanRequestContent } from '@/types/chat'
import type { TaskProgress } from '@/types/tasks'

function _extractProgress(tasks: { status: string }[]): TaskProgress {
  const total = tasks.length
  const counts = {
    pending: 0,
    running: 0,
    completed: 0,
    failed: 0,
    awaiting_human: 0,
  }
  tasks.forEach((task) => {
    if (task.status in counts) {
      counts[task.status as keyof typeof counts]++
    }
  })
  return {
    total,
    pending: counts.pending,
    running: counts.running,
    completed: counts.completed,
    failed: counts.failed,
    awaiting_human: counts.awaiting_human,
    percent: total > 0 ? Math.round((counts.completed / total) * 100) : 0,
  }
}

export function MessageList() {
  const { t } = useTranslation()
  const messages = useChatStore((state) => state.messages)
  const currentSessionId = useChatStore((state) => state.currentSessionId)
  const currentProjectId = useChatStore((state) => state.currentProjectId)
  const setMessages = useChatStore((state) => state.setMessages)
  const setIsTyping = useChatStore((state) => state.setIsTyping)
  const { setTaskTree, setProgress } = useTaskStore()
  const { loadPlan, discardDraft } = usePlanStore()
  const { setJobId, reset: resetExecution } = useExecutionStore()
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleRegenerate = async (messageId: string) => {
    if (!currentSessionId || !currentProjectId) return
    setRegeneratingId(messageId)
    setIsTyping(true)
    try {
      const response = await chatApi.regenerate({
        project_id: currentProjectId,
        session_id: currentSessionId,
        message: '',
      })

      const tasks = response.data.task_tree.tasks
      setTaskTree(tasks)
      setProgress(_extractProgress(tasks))

      if (response.data.status === 'awaiting_plan_approval' && response.data.plan) {
        const planContent: PlanRequestContent = {
          plan_id: response.data.plan_id || response.data.plan.plan_id,
          response_text: response.data.response,
          plan: response.data.plan,
        }
        loadPlan(planContent)
      } else {
        discardDraft()
      }

      setMessages(response.data.messages)

      if (response.data.job_id) {
        resetExecution()
        setJobId(response.data.job_id)
        setTaskTree(tasks)
        setProgress(_extractProgress(tasks))
      }
    } catch (error: any) {
      toastError(error?.response?.data?.detail || t('chat.sendFailedShort'))
    } finally {
      setIsTyping(false)
      setRegeneratingId(null)
    }
  }

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center overflow-y-auto p-4">
        <EmptyState
          icon={Sparkles}
          title={t('chat.emptyTitle')}
          description={t('chat.emptyDesc')}
        />
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="mx-auto max-w-3xl space-y-2">
        {messages.map((message, index) => (
          <MessageBubble
            key={message.id}
            message={message}
            onRegenerate={
              message.sender === 'agent' &&
              index === messages.length - 1 &&
              regeneratingId !== message.id
                ? () => handleRegenerate(message.id)
                : undefined
            }
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
