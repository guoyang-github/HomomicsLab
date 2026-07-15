import { useEffect, useState, useMemo } from 'react'
import { clsx } from 'clsx'
import { Loader2, Workflow, X } from 'lucide-react'
import { useTaskStore } from '@/stores/taskStore'
import { useExecutionStore } from '@/stores/executionStore'
import { useOverlayStore } from '@/stores/overlayStore'
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

export function TodoChecklist() {
  const { t } = useTranslation()
  const tasks = useTaskStore((state) => state.tasks)
  const status = useExecutionStore((state) => state.status)
  const openWorkflow = useOverlayStore((state) => state.openWorkflow)
  const [hidden, setHidden] = useState(false)

  useEffect(() => {
    if (status === 'completed' || status === 'aborted' || status === 'failed') {
      const timer = setTimeout(() => setHidden(true), 2500)
      return () => clearTimeout(timer)
    }
    setHidden(false)
  }, [status])

  const items = useMemo(() => flattenTasks(tasks), [tasks])

  if (hidden) return null
  if (items.length === 0 && status === 'idle') return null

  const isTerminal = status === 'completed' || status === 'aborted' || status === 'failed'
  const completedCount = items.filter((item) => item.status === 'completed').length
  const failedCount = items.filter((item) => item.status === 'failed').length
  const visibleItems = items.slice(0, 6)

  return (
    <div className="mx-auto w-full max-w-[780px] px-6 pb-2">
      <div className="rounded-xl border border-border-faint bg-surface px-3 py-2 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            {!isTerminal && <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />}
            <span className="text-xs font-medium text-foreground">
              {isTerminal
                ? t('executionLog.completed')
                : `${t('executionLog.running')} · ${completedCount}/${items.length}`}
            </span>
            {failedCount > 0 && (
              <span className="text-xs text-error">{failedCount} failed</span>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={() => openWorkflow()}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-accent transition-colors hover:bg-accent/10"
            >
              <Workflow className="h-3.5 w-3.5" />
              {t('todoList.viewWorkflow')}
            </button>
            {isTerminal && (
              <button
                type="button"
                onClick={() => setHidden(true)}
                className="rounded p-1 text-muted-foreground hover:bg-surface-2 hover:text-foreground"
                title={t('common.close')}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>

        <div className="mt-1.5 space-y-0.5">
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
        </div>
      </div>
    </div>
  )
}
