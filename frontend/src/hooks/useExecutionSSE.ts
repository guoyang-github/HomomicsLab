import { useEffect, useRef } from 'react'
import { useExecutionStore } from '@/stores/executionStore'
import { useTaskStore } from '@/stores/taskStore'
import { useTranslation } from '@/i18n'

export function useExecutionSSE(jobId: string | null) {
  const { t } = useTranslation()
  const eventSourceRef = useRef<EventSource | null>(null)
  const addLog = useExecutionStore((state) => state.addLog)
  const setConnected = useExecutionStore((state) => state.setConnected)
  const setStatus = useExecutionStore((state) => state.setStatus)
  const updateTaskStatus = useTaskStore((state) => state.updateTaskStatus)

  useEffect(() => {
    if (!jobId) {
      eventSourceRef.current?.close()
      setConnected(false)
      return
    }

    const url = `/api/execution/${jobId}/status`
    const es = new EventSource(url)
    eventSourceRef.current = es

    es.onopen = () => {
      setConnected(true)
    }

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.type === 'status' && data.task_id && data.status) {
          updateTaskStatus(data.task_id, data.status)
          setStatus(data.overall_status || 'running', data.percent)
        }

        if (data.type === 'log') {
          addLog({
            timestamp: data.timestamp || new Date().toISOString(),
            level: data.level || 'info',
            message: data.message,
            taskId: data.task_id,
          })
        }

        if (data.type === 'stdout') {
          addLog({
            timestamp: new Date().toISOString(),
            level: 'stdout',
            message: data.message,
            taskId: data.task_id,
          })
        }

        if (data.type === 'stderr') {
          addLog({
            timestamp: new Date().toISOString(),
            level: 'stderr',
            message: data.message,
            taskId: data.task_id,
          })
        }

        if (data.type === 'complete') {
          setStatus('completed', 100)
          es.close()
          setConnected(false)
        }

        if (data.type === 'error' || data.type === 'failed') {
          setStatus('failed')
          addLog({
            timestamp: new Date().toISOString(),
            level: 'error',
            message: data.message || t('execution.failed'),
          })
          es.close()
          setConnected(false)
        }
      } catch {
        addLog({
          timestamp: new Date().toISOString(),
          level: 'info',
          message: event.data,
        })
      }
    }

    es.onerror = () => {
      setConnected(false)
      es.close()
    }

    return () => {
      es.close()
      setConnected(false)
    }
  }, [jobId, addLog, setConnected, setStatus, updateTaskStatus, t])
}
