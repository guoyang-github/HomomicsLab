import { useEffect, useRef } from 'react'
import { useExecutionStore } from '@/stores/executionStore'
import { useTaskStore } from '@/stores/taskStore'
import { useTranslation } from '@/i18n'
import type { TaskNode, TaskProgress } from '@/types/tasks'

interface ExecutionStatePayload {
  job_id: string
  status: string
  current_phase?: string
  progress_pct: number
  error_message?: string | null
  tasks?: TaskNode[]
  active_task_id?: string | null
}

const MAX_RECONNECT_RETRIES = 5
const RECONNECT_BASE_DELAY_MS = 1000

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
  const retryCountRef = useRef(0)
  const addLog = useExecutionStore((state) => state.addLog)
  const setConnected = useExecutionStore((state) => state.setConnected)
  const setStatus = useExecutionStore((state) => state.setStatus)
  const setTaskTree = useTaskStore((state) => state.setTaskTree)
  const setProgress = useTaskStore((state) => state.setProgress)

  useEffect(() => {
    if (!jobId) {
      eventSourceRef.current?.close()
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      retryCountRef.current = 0
      setConnected(false)
      return
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

          const status = data.status.toLowerCase()
          const isTerminal = status === 'completed' || status === 'failed' || status === 'cancelled'

          if (data.tasks && data.tasks.length > 0) {
            setTaskTree(data.tasks)
            setProgress(buildProgress(data.tasks))
          }

          if (data.active_task_id) {
            addLog({
              timestamp: new Date().toISOString(),
              level: 'info',
              message: `${data.current_phase || data.active_task_id}`,
              taskId: data.active_task_id,
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

          if (data.error_message) {
            addLog({
              timestamp: new Date().toISOString(),
              level: 'error',
              message: data.error_message,
              taskId: data.active_task_id || undefined,
            })
          }

          if (isTerminal) {
            es.close()
            setConnected(false)
            addLog({
              timestamp: new Date().toISOString(),
              level: status === 'completed' ? 'success' : 'error',
              message: status === 'completed' ? t('executionLog.completed') : t('executionLog.failed'),
            })
          }
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
        }
      }
    }

    connect()

    return () => {
      eventSourceRef.current?.close()
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
    }
  }, [jobId, addLog, setConnected, setStatus, setTaskTree, setProgress, t])
}
