import { useEffect, useRef } from 'react'
import { useExecutionStore } from '@/stores/executionStore'
import { useTaskStore } from '@/stores/taskStore'
import { useTranslation } from '@/i18n'
import type { TaskNode, TaskProgress, TaskStatus } from '@/types/tasks'

interface ExecutionStatePayload {
  job_id: string
  status: string
  current_phase?: string
  progress_pct: number
  error_message?: string | null
  tasks?: TaskNode[]
  active_task_id?: string | null
  result?: Record<string, any> | null
}

const MAX_RECONNECT_RETRIES = 5
const RECONNECT_BASE_DELAY_MS = 1000
const POLL_INTERVAL_MS = 3000

function buildProgress(tasks: TaskNode[]): TaskProgress {
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

export function useExecutionSSE(jobId: string | null) {
  const { t } = useTranslation()
  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const retryCountRef = useRef(0)
  const addLog = useExecutionStore((state) => state.addLog)
  const setConnected = useExecutionStore((state) => state.setConnected)
  const setStatus = useExecutionStore((state) => state.setStatus)
  const setResult = useExecutionStore((state) => state.setResult)
  const setTaskTree = useTaskStore((state) => state.setTaskTree)
  const updateTaskStatus = useTaskStore((state) => state.updateTaskStatus)
  const setProgress = useTaskStore((state) => state.setProgress)
  const tasksRef = useRef<TaskNode[]>([])
  const tasks = useTaskStore((state) => state.tasks)
  useEffect(() => {
    tasksRef.current = tasks
  }, [tasks])

  useEffect(() => {
    if (!jobId) {
      eventSourceRef.current?.close()
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current)
        pollTimerRef.current = null
      }
      retryCountRef.current = 0
      setConnected(false)
      return
    }

    function applyPayload(data: ExecutionStatePayload) {
      const status = data.status.toLowerCase()
      const isTerminal = status === 'completed' || status === 'failed' || status === 'cancelled'

      if (data.tasks && data.tasks.length > 0) {
        setTaskTree(data.tasks)
        setProgress(buildProgress(data.tasks))
        // Some agentic runs nest the final skill result inside the task tree
        // rather than the top-level result field. Extract it so the result card
        // renders even if the job-level result event is skipped.
        const completedTask = data.tasks.find(
          (t) =>
            (t.status === 'completed' || t.status === 'failed') &&
            t.result &&
            typeof t.result === 'object'
        )
        if (completedTask?.result) {
          // eslint-disable-next-line no-console
          console.log('[useExecutionSSE] setResult from task', JSON.parse(JSON.stringify(completedTask.result)))
          setResult(completedTask.result as Record<string, any>)
        }
      } else if (data.active_task_id || isTerminal) {
        // Agentic skills stream state events without a full task tree.
        // Drive the active task's status from the job state so the
        // TODO list and progress bar update in real time.
        const taskStatus: TaskStatus = isTerminal
          ? status === 'completed'
            ? 'completed'
            : 'failed'
          : status === 'running'
          ? 'running'
          : status === 'awaiting_human'
          ? 'awaiting_human'
          : 'pending'
        const targetIds = data.active_task_id
          ? [data.active_task_id]
          : tasksRef.current.map((t) => t.id)
        targetIds.forEach((taskId) => updateTaskStatus(taskId, taskStatus))
        const updatedTasks = tasksRef.current.map((t) =>
          targetIds.includes(t.id) ? ({ ...t, status: taskStatus } as TaskNode) : t
        )
        setProgress(buildProgress(updatedTasks))
      }

      if (data.active_task_id || data.current_phase) {
        addLog({
          timestamp: new Date().toISOString(),
          level: 'info',
          message: `${data.current_phase || data.active_task_id}`,
          taskId: data.active_task_id || undefined,
        })
      }

      setStatus(
        status === 'completed'
          ? 'completed'
          : status === 'failed' || status === 'cancelled'
          ? 'failed'
          : status === 'awaiting_human'
          ? 'running'
          : 'running',
        data.progress_pct
      )

      if (data.result) {
        // eslint-disable-next-line no-console
        console.log('[useExecutionSSE] setResult', JSON.parse(JSON.stringify(data.result)))
        setResult(data.result)
      }

      if (data.error_message) {
        addLog({
          timestamp: new Date().toISOString(),
          level: 'error',
          message: data.error_message,
          taskId: data.active_task_id || undefined,
        })
      }

      if (isTerminal) {
        eventSourceRef.current?.close()
        if (pollTimerRef.current) {
          clearInterval(pollTimerRef.current)
          pollTimerRef.current = null
        }
        setConnected(false)
        addLog({
          timestamp: new Date().toISOString(),
          level: status === 'completed' ? 'success' : 'error',
          message: status === 'completed' ? t('executionLog.completed') : t('executionLog.failed'),
        })
        // If no result was delivered via SSE, fetch the persisted trace once.
        fetchTraceResult()
      }

      return isTerminal
    }

    async function fetchTraceResult() {
      try {
        const res = await fetch(`/api/execution/${jobId}/trace`)
        if (!res.ok) return
        const trace = await res.json()
        const resultNode =
          trace.nodes?.find((n: any) => n.outputs?.result?.success !== undefined) ||
          trace.nodes?.find((n: any) => n.outputs?.success !== undefined) ||
          trace.nodes?.find((n: any) => n.outputs?.result?.status === 'failure') ||
          trace.nodes?.find((n: any) => n.node_id === 'root')
        const outputs = resultNode?.outputs
        if (outputs) {
          if (outputs.result) {
            // eslint-disable-next-line no-console
            console.log('[useExecutionSSE] setResult from trace', JSON.parse(JSON.stringify(outputs.result)))
            setResult(outputs.result)
          } else if (outputs.success !== undefined) {
            setResult(outputs)
          }
        }
      } catch {
        // Ignore transient trace fetch errors.
      }
    }

    function connect() {
      const url = `/api/execution/${jobId}/events`
      const es = new EventSource(url)
      eventSourceRef.current = es

      es.onopen = () => {
        retryCountRef.current = 0
        setConnected(true)
        addLog({
          timestamp: new Date().toISOString(),
          level: 'info',
          message: t('executionLog.running') + ` (${(jobId as string).slice(0, 8)})`,
        })
      }

      es.addEventListener('state', (event) => {
        try {
          const data: ExecutionStatePayload = JSON.parse(event.data)
          applyPayload(data)
        } catch {
          addLog({
            timestamp: new Date().toISOString(),
            level: 'info',
            message: event.data,
          })
        }
      })

      es.onerror = () => {
        setConnected(false)
        es.close()

        if (retryCountRef.current < MAX_RECONNECT_RETRIES) {
          const delay = RECONNECT_BASE_DELAY_MS * 2 ** retryCountRef.current
          retryCountRef.current += 1
          addLog({
            timestamp: new Date().toISOString(),
            level: 'warning',
            message: t('executionLog.reconnecting', {
              count: retryCountRef.current,
              max: MAX_RECONNECT_RETRIES,
              delay,
            }) || `SSE disconnected. Reconnecting in ${delay}ms (attempt ${retryCountRef.current}/${MAX_RECONNECT_RETRIES})...`,
          })
          reconnectTimerRef.current = setTimeout(connect, delay)
        } else {
          addLog({
            timestamp: new Date().toISOString(),
            level: 'error',
            message: t('executionLog.reconnectFailed') || 'SSE connection lost and reconnect limit reached.',
          })
          startPolling()
        }
      }
    }

    function startPolling() {
      if (pollTimerRef.current) return
      addLog({
        timestamp: new Date().toISOString(),
        level: 'warning',
        message: 'SSE unavailable; falling back to polling.',
      })

      async function poll() {
        try {
          const res = await fetch(`/api/execution/${jobId}/trace`)
          if (!res.ok) return
          const trace = await res.json()
          const status = String(trace.status || 'running').toLowerCase()
          const isTerminal = status === 'completed' || status === 'failed' || status === 'cancelled'

          setStatus(
            status === 'completed'
              ? 'completed'
              : status === 'failed' || status === 'cancelled'
              ? 'failed'
              : 'running',
            isTerminal ? 100 : 50
          )

          if (trace.error_message) {
            addLog({
              timestamp: new Date().toISOString(),
              level: 'error',
              message: trace.error_message,
            })
          }

          // Try to extract the final skill result from any completed node.
          const resultNode =
            trace.nodes?.find((n: any) => n.outputs?.result?.success !== undefined) ||
            trace.nodes?.find((n: any) => n.outputs?.success !== undefined) ||
            trace.nodes?.find((n: any) => n.node_id === 'root')
          const outputs = resultNode?.outputs
          if (outputs) {
            if (outputs.result) {
              setResult(outputs.result)
            } else if (outputs.success !== undefined) {
              setResult(outputs)
            }
          }

          if (isTerminal) {
            if (pollTimerRef.current) {
              clearInterval(pollTimerRef.current)
              pollTimerRef.current = null
            }
            setConnected(false)
            addLog({
              timestamp: new Date().toISOString(),
              level: status === 'completed' ? 'success' : 'error',
              message: status === 'completed' ? t('executionLog.completed') : t('executionLog.failed'),
            })
          }
        } catch {
          // Ignore transient polling errors.
        }
      }

      poll()
      pollTimerRef.current = setInterval(poll, POLL_INTERVAL_MS)
    }

    connect()

    return () => {
      eventSourceRef.current?.close()
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current)
        pollTimerRef.current = null
      }
    }
  }, [jobId, addLog, setConnected, setStatus, setResult, setTaskTree, updateTaskStatus, setProgress, t])
}
