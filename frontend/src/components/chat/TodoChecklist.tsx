import { useEffect, useState } from 'react'
import { clsx } from 'clsx'
import { Loader2, Workflow, X } from 'lucide-react'
import { useTaskStore } from '@/stores/taskStore'
import { useExecutionStore } from '@/stores/executionStore'
import { useOverlayStore } from '@/stores/overlayStore'
import { useTranslation } from '@/i18n'
import type { TaskNode } from '@/types/tasks'

const statusIcons: Record<TaskNode['status'], string> = {
  pending: '⬜',
  running: '▶️',
  completed: '✅',
  failed: '❌',
  awaiting_human: '⏸️',
  aborted: '🚫',
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

  if (hidden) return null
  if (tasks.length === 0 && status === 'idle') return null

  const isTerminal = status === 'completed' || status === 'aborted' || status === 'failed'
  const completedCount = tasks.filter((task) => task.status === 'completed').length
  const failedCount = tasks.filter((task) => task.status === 'failed').length
  const visibleTasks = tasks.slice(0, 5)

  return (
    <div className="mx-auto w-full max-w-[780px] px-6 pb-2">
      <div className="rounded-xl border border-border-faint bg-surface px-3 py-2 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            {!isTerminal && <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />}
            <span className="text-xs font-medium text-foreground">
              {isTerminal
                ? t('executionLog.completed')
                : `${t('executionLog.running')} · ${completedCount}/${tasks.length}`}
            </span>
            {failedCount > 0 && (
              <span className="text-xs text-error">{failedCount} {failedCount === 1 ? 'failed' : 'failed'}</span>
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
          {visibleTasks.map((task) => (
            <div key={task.id} className="flex items-center gap-2 text-xs">
              <span className="shrink-0">{statusIcons[task.status]}</span>
              <span
                className={clsx(
                  'flex-1 truncate',
                  task.status === 'completed' && 'text-muted-foreground line-through',
                  task.status === 'failed' && 'text-error'
                )}
                title={task.description}
              >
                {task.description}
              </span>
            </div>
          ))}
          {tasks.length > visibleTasks.length && (
            <div className="pl-5 text-[10px] text-muted-foreground">
              +{tasks.length - visibleTasks.length} more
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
