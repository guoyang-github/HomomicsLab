import { useEffect, useState, useMemo } from 'react'
import { clsx } from 'clsx'
import { Loader2, ChevronDown, ChevronUp, CheckCircle2, AlertCircle, Workflow } from 'lucide-react'
import { useTaskStore } from '@/stores/taskStore'
import { useExecutionStore } from '@/stores/executionStore'
import { useChatStore } from '@/stores/chatStore'
import { useOverlayStore } from '@/stores/overlayStore'
import { usePlanStore } from '@/stores/planStore'
import { useTranslation } from '@/i18n'
import type { TaskNode, TaskStatus } from '@/types/tasks'

const statusIcons: Record<TaskNode['status'], string> = {
  pending: '⬜',
  running: '▶️',
  completed: '✅',
  failed: '❌',
  awaiting_human: '⏸️',
  aborted: '🚫',
}

interface DisplaySubtask {
  id: string
  description: string
  analysis_type?: string
}

interface FlattenedItem {
  id: string
  description: string
  status: TaskStatus
  isSubtask: boolean
}

function getDisplaySubtasks(task: TaskNode): DisplaySubtask[] | null {
  const raw = task.parameters?.display_subtasks
  if (!Array.isArray(raw) || raw.length === 0) return null
  return raw.filter(
    (s): s is DisplaySubtask =>
      typeof s === 'object' &&
      s !== null &&
      typeof (s as DisplaySubtask).id === 'string' &&
      typeof (s as DisplaySubtask).description === 'string'
  )
}

function flattenTasks(tasks: TaskNode[]): FlattenedItem[] {
  const items: FlattenedItem[] = []
  for (const task of tasks) {
    const subtasks = getDisplaySubtasks(task)
    if (subtasks && subtasks.length >= 2) {
      for (const sub of subtasks) {
        items.push({
          id: sub.id,
          description: sub.description,
          status: task.status,
          isSubtask: true,
        })
      }
    } else {
      items.push({
        id: task.id,
        description: task.description,
        status: task.status,
        isSubtask: false,
      })
    }
  }
  return items
}

function deriveGroupStatus(tasks: TaskNode[]): 'running' | 'completed' | 'failed' | 'idle' {
  if (tasks.length === 0) return 'idle'
  if (tasks.some((t) => t.status === 'running')) return 'running'
  if (tasks.some((t) => t.status === 'failed')) return 'failed'
  if (tasks.every((t) => t.status === 'completed')) return 'completed'
  return 'running'
}

export function TodoChecklist() {
  const { t } = useTranslation()
  const tasks = useTaskStore((state) => state.tasks)
  const status = useExecutionStore((state) => state.status)
  const jobSessionId = useExecutionStore((state) => state.jobSessionId)
  const currentSessionId = useChatStore((state) => state.currentSessionId)
  const [expanded, setExpanded] = useState(false)
  const openWorkflow = useOverlayStore((state) => state.openWorkflow)
  const discardDraft = usePlanStore((state) => state.discardDraft)

  // Keep the floating TODO scoped to the current session. This prevents the
  // old session's task list from flashing when the user switches sessions.
  const isJobForCurrentSession = !jobSessionId || jobSessionId === currentSessionId

  const items = useMemo(() => flattenTasks(tasks), [tasks])
  const groupStatus = useMemo(() => deriveGroupStatus(tasks), [tasks])

  // Auto-expand while running so the user sees live progress; collapse by
  // default when done to avoid covering the chat content.
  useEffect(() => {
    if (status === 'running' || groupStatus === 'running') {
      setExpanded(true)
    } else if (groupStatus === 'completed' || groupStatus === 'failed') {
      setExpanded(false)
    }
  }, [status, groupStatus])

  // Show the floating TODO whenever the current session has tasks.
  if (!isJobForCurrentSession) return null
  if (items.length === 0) return null

  const failedCount = items.filter((item) => item.status === 'failed').length
  const completedCount = items.filter((item) => item.status === 'completed').length
  const visibleItems = items.slice(0, 8)

  const isRunning = groupStatus === 'running'
  const isFailed = groupStatus === 'failed'
  const isCompleted = groupStatus === 'completed'

  return (
    <div data-testid="todo-checklist" className="absolute right-3 top-3 z-30 w-60 rounded-lg border border-border bg-card/95 px-2.5 py-1.5 shadow-md backdrop-blur-sm">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="flex w-full items-center justify-between gap-2"
      >
        <div className="flex min-w-0 items-center gap-2">
          {isRunning ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />
          ) : isFailed ? (
            <AlertCircle className="h-3.5 w-3.5 text-error" />
          ) : isCompleted ? (
            <CheckCircle2 className="h-3.5 w-3.5 text-success" />
          ) : (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />
          )}
          <span className="text-xs font-medium text-foreground">
            {isRunning
              ? `${t('executionLog.running')} · ${completedCount}/${items.length}`
              : isFailed
              ? `${t('executionLog.failed')} · ${completedCount}/${items.length}`
              : isCompleted
              ? `${t('executionLog.completed')} · ${items.length}`
              : `${t('executionLog.running')} · ${completedCount}/${items.length}`}
          </span>
          {failedCount > 0 && (
            <span className="text-xs text-error">{failedCount} failed</span>
          )}
        </div>
        <div className="flex shrink-0 items-center">
          {expanded ? (
            <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="mt-1.5 max-h-72 space-y-0.5 overflow-y-auto">
          {visibleItems.map((item) => (
            <div key={item.id} className="flex items-center gap-2 text-xs">
              <span className="shrink-0">{statusIcons[item.status]}</span>
              <span
                className={clsx(
                  'flex-1 truncate',
                  item.status === 'completed' && 'text-muted-foreground line-through',
                  item.status === 'failed' && 'text-error',
                  item.isSubtask && 'pl-2'
                )}
                title={item.description}
              >
                {item.description}
              </span>
            </div>
          ))}
          {items.length > visibleItems.length && (
            <div className="pl-5 text-[10px] text-muted-foreground">
              +{items.length - visibleItems.length} more
            </div>
          )}

          <button
            type="button"
            onClick={() => {
              discardDraft()
              openWorkflow()
            }}
            className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-accent transition-colors hover:bg-accent/10"
          >
            <Workflow className="h-3.5 w-3.5" />
            {t('todoList.viewWorkflow')}
          </button>
        </div>
      )}
    </div>
  )
}
