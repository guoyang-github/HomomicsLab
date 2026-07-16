import { useEffect, useMemo, useState } from 'react'
import { clsx } from 'clsx'
import {
  Activity,
  ChevronDown,
  ChevronUp,
  Square,
  Workflow,
  X,
} from 'lucide-react'
import { useTaskStore } from '@/stores/taskStore'
import { useExecutionStore } from '@/stores/executionStore'
import { useOverlayStore } from '@/stores/overlayStore'
import { useTranslation } from '@/i18n'
import { executionApi } from '@/sdk'
import type { TaskNode } from '@/types/tasks'

const statusIcons: Record<TaskNode['status'], string> = {
  pending: '⬜',
  running: '▶️',
  completed: '✅',
  failed: '❌',
  awaiting_human: '⏸️',
  aborted: '🚫',
}

export function ExecutionProgressBar() {
  const { t } = useTranslation()
  const tasks = useTaskStore((state) => state.tasks)
  const progress = useTaskStore((state) => state.progress)
  const selectedTaskId = useTaskStore((state) => state.selectedTaskId)
  const selectTask = useTaskStore((state) => state.selectTask)

  const status = useExecutionStore((state) => state.status)
  const jobId = useExecutionStore((state) => state.jobId)
  const isConnected = useExecutionStore((state) => state.isConnected)
  const logs = useExecutionStore((state) => state.logs)
  const livePhase = useExecutionStore((state) => state.currentPhase)

  const openWorkflow = useOverlayStore((state) => state.openWorkflow)

  const [expanded, setExpanded] = useState(false)
  const [dismissed, setDismissed] = useState(false)
  const [cancelling, setCancelling] = useState(false)

  useEffect(() => {
    // Reset dismissal when a new job starts.
    if (jobId) {
      setDismissed(false)
    }
  }, [jobId])

  const isRunning = status === 'running'
  const isTerminal = status === 'completed' || status === 'failed' || status === 'aborted'

  const currentTask = useMemo(() => {
    if (tasks.length === 0) return null
    return (
      tasks.find((t) => t.status === 'running') ||
      tasks.slice().reverse().find((t) => t.status === 'completed') ||
      tasks.find((t) => t.status !== 'completed') ||
      tasks[0]
    )
  }, [tasks])

  const currentPhase = livePhase || currentTask?.phase || currentTask?.description || ''

  const livePercent = useExecutionStore((state) => state.percent)

  const derivedProgress = useMemo(() => {
    if (progress && progress.total > 0) {
      // Blend the task-tree percent with the live sub-step percent so a single
      // long-running step still shows motion (e.g. 15%/60%/90% from CodeAct).
      const base = progress.percent
      const live = typeof livePercent === 'number' ? livePercent : base
      return {
        ...progress,
        percent: Math.max(base, live),
      }
    }
    const total = tasks.length
    const completed = tasks.filter((t) => t.status === 'completed').length
    return {
      total,
      pending: 0,
      running: 0,
      completed,
      failed: 0,
      awaiting_human: 0,
      percent: total > 0 ? Math.round((completed / total) * 100) : 0,
    }
  }, [progress, tasks, livePercent])

  if (dismissed) return null
  if (tasks.length === 0 && status === 'idle') return null

  const handleCancel = async () => {
    if (!jobId || !isRunning) return
    setCancelling(true)
    try {
      await executionApi.cancel(jobId)
    } catch {
      // ignore; SSE will reflect terminal state
    }
  }

  const handleViewWorkflow = () => {
    openWorkflow()
  }

  const recentLog = logs[logs.length - 1]

  return (
    <div className="shrink-0 px-4 pt-3">
      <div className="mx-auto w-full max-w-[780px] overflow-hidden rounded-xl border border-border-faint bg-surface shadow-sm">
        {isTerminal ? (
          <div className="flex items-center justify-between px-3 py-2">
            <div className="flex items-center gap-2.5">
              <StatusDot status={status} />
              <span className="text-sm font-medium text-foreground">
                {status === 'completed' ? t('executionLog.completed') : t('executionLog.failed')}
              </span>
              <span className="text-xs text-muted-foreground">
                {derivedProgress.completed}/{derivedProgress.total} {t('progress.steps', { count: derivedProgress.total })}
              </span>
              {isConnected && <Activity className="h-3 w-3 animate-pulse text-success" />}
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={handleViewWorkflow}
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-accent transition-colors hover:bg-accent/10"
              >
                <Workflow className="h-3.5 w-3.5" />
                {t('todoList.viewWorkflow')}
              </button>
              <button
                type="button"
                onClick={() => setDismissed(true)}
                className="rounded p-1 text-muted-foreground hover:bg-surface-2 hover:text-foreground"
                title={t('common.close')}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between px-3 py-2">
              <div className="flex min-w-0 items-center gap-3">
                <StatusDot status={status} />
                {currentPhase && (
                  <span className="truncate rounded-full border border-border-faint bg-surface-2 px-2 py-0.5 text-xs font-medium text-foreground">
                    {currentPhase}
                  </span>
                )}
                <div className="hidden items-center gap-2 sm:flex">
                  <div className="h-1.5 w-16 overflow-hidden rounded-full bg-surface-2">
                    <div
                      className="h-full rounded-full bg-accent transition-all"
                      style={{ width: `${derivedProgress.percent}%` }}
                    />
                  </div>
                  <span className="text-xs font-medium text-muted-foreground">
                    {derivedProgress.percent}%
                  </span>
                </div>
                {recentLog && (
                  <span className="hidden max-w-[180px] truncate text-xs text-muted-foreground md:inline">
                    {recentLog.message}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                {isRunning && (
                  <button
                    type="button"
                    onClick={handleCancel}
                    disabled={cancelling}
                    className="inline-flex items-center gap-1 rounded-md border border-error/30 px-2 py-1 text-xs font-medium text-error transition-colors hover:bg-error/10 disabled:opacity-50"
                  >
                    <Square className="h-3 w-3 fill-current" />
                    {cancelling ? '…' : t('workflow.abort')}
                  </button>
                )}
                <button
                  type="button"
                  onClick={handleViewWorkflow}
                  className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-accent transition-colors hover:bg-accent/10"
                >
                  <Workflow className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">{t('todoList.viewWorkflow')}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setExpanded((e) => !e)}
                  className="rounded p-1 text-muted-foreground hover:bg-surface-2 hover:text-foreground"
                  title={expanded ? t('executionLog.collapse') : t('executionLog.expand')}
                >
                  {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {expanded && (
              <div className="border-t border-border-faint px-3 py-2">
                <div className="space-y-0.5">
                  {tasks.map((task) => {
                    const isSelected = selectedTaskId === task.id
                    return (
                      <button
                        key={task.id}
                        type="button"
                        onClick={() => selectTask(isSelected ? null : task.id)}
                        className={clsx(
                          'flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-xs transition-colors',
                          isSelected ? 'bg-accent/10 text-accent' : 'hover:bg-surface-2'
                        )}
                      >
                        <span className="shrink-0">{statusIcons[task.status]}</span>
                        <span className="flex-1 truncate">{task.description}</span>
                        <span className="shrink-0 text-[10px] text-muted-foreground">{task.phase}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function StatusDot({ status }: { status: string }) {
  return (
    <span
      className={clsx(
        'h-2 w-2 shrink-0 rounded-full',
        status === 'running' && 'animate-pulse bg-success',
        status === 'completed' && 'bg-success',
        status === 'failed' && 'bg-error',
        status === 'aborted' && 'bg-warning',
        status === 'idle' && 'bg-muted-foreground/50'
      )}
    />
  )
}
