import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { useChatStore } from '@/stores/chatStore'
import { useTaskStore } from '@/stores/taskStore'
import { usePlanStore } from '@/stores/planStore'
import { useExecutionStore } from '@/stores/executionStore'
import { MessageBubble } from './MessageBubble'
import { EmptyState } from '@/components/ui'
import { Avatar, AvatarFallback } from '@/components/ui/shadcn/avatar'
import { Bot, Sparkles } from 'lucide-react'
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
  const isTyping = useChatStore((state) => state.isTyping)
  const currentSessionId = useChatStore((state) => state.currentSessionId)
  const currentProjectId = useChatStore((state) => state.currentProjectId)
  const setMessages = useChatStore((state) => state.setMessages)
  const setIsTyping = useChatStore((state) => state.setIsTyping)
  const { setTaskTree, setProgress } = useTaskStore()
  const { loadPlan, discardDraft } = usePlanStore()
  const { startJob } = useExecutionStore()
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
        startJob(response.data.job_id, currentSessionId)
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
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-[780px] space-y-8 px-6 py-8">
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
        {isTyping && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, ease: [0.2, 0, 0, 1] }}
            className="flex gap-3 sm:gap-4"
          >
            <Avatar className="mt-0.5 h-8 w-8 shrink-0 border border-border">
              <AvatarFallback className="bg-muted text-muted-foreground">
                <Bot className="h-4 w-4" />
              </AvatarFallback>
            </Avatar>
            <div className="flex items-center gap-1.5 pt-2.5" aria-label={t('chat.agentThinking')}>
              {[0, 150, 300].map((delay) => (
                <span
                  key={delay}
                  className="h-2 w-2 animate-pulse rounded-full bg-muted-foreground/50"
                  style={{ animationDelay: `${delay}ms` }}
                />
              ))}
            </div>
          </motion.div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
