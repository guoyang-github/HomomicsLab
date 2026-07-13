import { useEffect, useRef } from 'react'
import { useExecutionStore } from '@/stores/executionStore'
import { useTaskStore } from '@/stores/taskStore'
import { useChatStore } from '@/stores/chatStore'
import { useTranslation } from '@/i18n'
import { executionApi } from '@/sdk'
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
  logs?: string[]
  resource_usage?: Record<string, any> | null
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

      if (data.logs && data.logs.length > 0) {
        data.logs.forEach((line) => {
          addLog({
            timestamp: new Date().toISOString(),
            level: 'stdout',
            message: line,
            taskId: data.active_task_id || undefined,
          })
        })
      }

      const agentEvents = data.resource_usage?.agent_events
      if (Array.isArray(agentEvents) && agentEvents.length > 0) {
        agentEvents.forEach((evt: any) => {
          if (!evt || typeof evt !== 'object') return
          const ts = evt.timestamp ? new Date(evt.timestamp * 1000).toISOString() : new Date().toISOString()
          const taskId = data.active_task_id || undefined
          if (evt.type === 'tool_start' && evt.tool) {
            const argText = evt.arguments?.summary
              ? evt.arguments.summary
              : JSON.stringify(evt.arguments || {})
            addLog({
              timestamp: ts,
              level: 'tool',
              message: `▶ ${evt.tool}${argText ? ` (${argText})` : ''}`,
              taskId,
            })
          } else if (evt.type === 'tool_end' && evt.tool) {
            const parts: string[] = [`✓ ${evt.tool}`]
            if (evt.success === false) parts.push('failed')
            if (evt.output) parts.push(evt.output)
            if (evt.error_message) parts.push(`error: ${evt.error_message}`)
            addLog({
              timestamp: ts,
              level: evt.success === false ? 'error' : 'tool',
              message: parts.join(' · '),
              taskId,
            })
          } else if (evt.type === 'artifact' && Array.isArray(evt.artifacts)) {
            evt.artifacts.forEach((path: string) => {
              addLog({
                timestamp: ts,
                level: 'artifact',
                message: `📄 ${path}`,
                taskId,
              })
            })
          } else if (evt.type === 'llm_retry') {
            addLog({
              timestamp: ts,
              level: 'warning',
              message: `模型调用失败，正在重试${evt.error_message ? `: ${evt.error_message}` : ''}`,
              taskId,
            })
          }
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
        // The backend appends the final summary message to the session when the
        // job finishes, but the SSE event can arrive before the message is
        // persisted. Refresh the current session messages so the answer appears
        // immediately without requiring a manual refresh or session switch.
        refreshSessionMessages()
      }

      return isTerminal
    }

    async function fetchTraceResult() {
      // The terminal SSE event can arrive just before the trace store has
      // persisted the final outputs. Retry a few times so the result card
      // renders reliably even when the worker finishes slightly after the
      // terminal state is published.
      const maxAttempts = 8
      for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
        try {
          const res = await executionApi.getTrace(jobId as string)
          const trace = res.data
          const resultNode =
            trace.nodes?.find((n: any) => n.outputs?.result?.success !== undefined) ||
            trace.nodes?.find((n: any) => n.outputs?.success !== undefined) ||
            trace.nodes?.find((n: any) => n.outputs?.result?.status === 'failure')
          const outputs = resultNode?.outputs
          if (outputs) {
            if (outputs.result) {
              // eslint-disable-next-line no-console
              console.log('[useExecutionSSE] setResult from trace', JSON.parse(JSON.stringify(outputs.result)))
              setResult(outputs.result)
              return
            } else if (outputs.success !== undefined) {
              setResult(outputs)
              return
            }
          }
        } catch {
          // Ignore transient trace fetch errors; retry.
        }
        await new Promise((r) => setTimeout(r, 500))
      }
    }

    async function refreshSessionMessages() {
      const jobSessionId = useExecutionStore.getState().jobSessionId
      if (!jobSessionId) {
        return
      }

      // Retry a few times in case the worker commits the summary message
      // slightly after publishing the terminal state.
      const maxAttempts = 6
      for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
        try {
          await useChatStore.getState().loadSessionMessages(jobSessionId)
          const currentSessionId = useChatStore.getState().currentSessionId
          // If the UI drifted away from the job's session (e.g. session list
          // sync overwrote currentSessionId), switch back so the result appears
          // in the conversation where the user asked the question.
          if (currentSessionId !== jobSessionId) {
            await useChatStore.getState().selectSession(jobSessionId)
          }
          const messages = useChatStore.getState().messages
          const lastMessage = messages[messages.length - 1]
          if (lastMessage && lastMessage.sender === 'agent' && lastMessage.type === 'text') {
            return
          }
        } catch (err) {
          // Ignore transient refresh errors.
        }
        await new Promise((r) => setTimeout(r, 500))
      }
    }

    function connect() {
      const url = executionApi.eventsUrl(jobId as string)
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
          const res = await executionApi.getTrace(jobId as string)
          const trace = res.data
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
