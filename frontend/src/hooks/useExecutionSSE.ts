import { useEffect, useRef } from 'react'
import { useExecutionStore } from '@/stores/executionStore'
import type { LogEntry } from '@/stores/executionStore'
import { useTaskStore } from '@/stores/taskStore'
import { useChatStore } from '@/stores/chatStore'
import { useTranslation } from '@/i18n'
import { executionApi } from '@/sdk'
import type { TaskNode, TaskProgress, TaskStatus } from '@/types/tasks'
import type { ChatMessage } from '@/types/chat'

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
  /** Chat messages injected by the backend (e.g. final result summary). */
  messages?: ChatMessage[]
  /** Present when the event originates from a sub-executor, e.g. "subagent:<skill_id>". */
  actor?: string
  /** Parent job/task id of the sub-executor; absent for top-level events. */
  parent_id?: string
}

/**
 * Domain-pipeline progress payloads (workflow skeleton + phase progress).
 * The backend streams them on the execution SSE channel; depending on the
 * final wiring they arrive either as a dedicated `progress` SSE event or
 * embedded in a `state` payload, so both entry points funnel into the same
 * handler.
 */
interface WorkflowProgressPayload {
  type?: string
  event?: string
  job_id?: string
  session_id?: string
  domain?: string
  phases?: Array<{ phase_type?: string; name?: string; skipped?: boolean }>
  phase?: string
  status?: string
  params?: Record<string, unknown>
}

/** Detect a workflow progress payload regardless of the SSE event name it
 * arrived on. */
function isWorkflowProgressPayload(data: unknown): data is WorkflowProgressPayload {
  if (!data || typeof data !== 'object') return false
  const evt = (data as WorkflowProgressPayload).event
  return evt === 'workflow_skeleton' || evt === 'phase'
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
  const setCurrentPhase = useExecutionStore((state) => state.setCurrentPhase)
  const setResult = useExecutionStore((state) => state.setResult)
  const setWorkflowSkeleton = useExecutionStore((state) => state.setWorkflowSkeleton)
  const setPhaseState = useExecutionStore((state) => state.setPhaseState)
  const setTaskTree = useTaskStore((state) => state.setTaskTree)
  const updateTaskStatus = useTaskStore((state) => state.updateTaskStatus)
  const setProgress = useTaskStore((state) => state.setProgress)
  const tasksRef = useRef<TaskNode[]>([])
  const tasks = useTaskStore((state) => state.tasks)
  useEffect(() => {
    tasksRef.current = tasks
  }, [tasks])
  const addMessage = useChatStore((state) => state.addMessage)
  const messagesRef = useRef<ChatMessage[]>([])
  const chatMessages = useChatStore((state) => state.messages)
  useEffect(() => {
    messagesRef.current = chatMessages
  }, [chatMessages])

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
      return
    }

    // All store writes below are scoped to this job; other sessions' jobs keep
    // streaming/retaining their own runtime state independently.
    const jid = jobId as string

    /**
     * Handle a domain-pipeline progress payload (see WorkflowProgressPayload).
     * Fault-tolerant by design: malformed entries are dropped silently so a
     * contract drift on the backend never breaks the main state stream.
     */
    function applyWorkflowProgress(data: WorkflowProgressPayload) {
      if (data.event === 'workflow_skeleton') {
        const domain = typeof data.domain === 'string' ? data.domain : ''
        const phases = Array.isArray(data.phases)
          ? data.phases
              .filter((p) => p && typeof p === 'object' && typeof p.phase_type === 'string' && p.phase_type)
              .map((p) => ({
                phase_type: p.phase_type as string,
                name: typeof p.name === 'string' && p.name ? p.name : (p.phase_type as string),
                skipped: p.skipped === true,
              }))
          : []
        if (!domain || phases.length === 0) return
        setWorkflowSkeleton(jid, { domain, phases })
        addLog(jid, {
          timestamp: new Date().toISOString(),
          level: 'info',
          message: t('executionLog.workflowSkeleton', { domain }) || `Workflow pipeline: ${domain}`,
        })
      } else if (data.event === 'phase') {
        if (typeof data.phase !== 'string' || !data.phase) return
        if (typeof data.status !== 'string' || !data.status) return
        const params =
          data.params && typeof data.params === 'object' && !Array.isArray(data.params)
            ? data.params
            : undefined
        setPhaseState(jid, data.phase, data.status, params)
      }
    }

    function applyPayload(data: ExecutionStatePayload) {
      const status = data.status.toLowerCase()
      const isTerminal = status === 'completed' || status === 'failed' || status === 'cancelled'
      const actor = typeof data.actor === 'string' && data.actor ? data.actor : undefined
      const parentId = typeof data.parent_id === 'string' && data.parent_id ? data.parent_id : undefined
      const isSubagentEvent = Boolean(actor)
      // Tag every log line produced by this event with its sub-executor so the
      // log panel can fold it into the parent group. Top-level events (no
      // actor) flow through unchanged.
      const pushLog = (entry: Omit<LogEntry, 'id'>) =>
        addLog(jid, actor ? { ...entry, actor, parentId } : entry)

      if (!isSubagentEvent && data.tasks && data.tasks.length > 0) {
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
          setResult(jid, completedTask.result as Record<string, any>)
        }
      }

      // Inject any chat messages broadcast by the backend (e.g. the final
      // result summary).  Skip messages already in the conversation.
      if (!isSubagentEvent && data.messages && data.messages.length > 0) {
        const existingIds = new Set(messagesRef.current.map((m) => m.id))
        data.messages.forEach((msg) => {
          if (!existingIds.has(msg.id)) {
            addMessage(msg)
          }
        })
      }

      if (!isSubagentEvent && (data.active_task_id || isTerminal)) {
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

      if (data.current_phase) {
        setCurrentPhase(jid, data.current_phase)
      }

      const isRetrying = status === 'retrying'
      if (data.active_task_id || data.current_phase) {
        pushLog({
          timestamp: new Date().toISOString(),
          level: isRetrying ? 'warning' : 'info',
          message: `${data.current_phase || data.active_task_id}`,
          taskId: data.active_task_id || undefined,
        })
      }

      if (isRetrying && data.error_message) {
        pushLog({
          timestamp: new Date().toISOString(),
          level: 'warning',
          message: `自动修正中：${data.error_message}`,
          taskId: data.active_task_id || undefined,
        })
      }

      if (data.logs && data.logs.length > 0) {
        data.logs.forEach((line) => {
          pushLog({
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
            pushLog({
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
            pushLog({
              timestamp: ts,
              level: evt.success === false ? 'error' : 'tool',
              message: parts.join(' · '),
              taskId,
            })
          } else if (evt.type === 'artifact' && Array.isArray(evt.artifacts)) {
            evt.artifacts.forEach((path: string) => {
              pushLog({
                timestamp: ts,
                level: 'artifact',
                message: `📄 ${path}`,
                taskId,
              })
            })
          } else if (evt.type === 'llm_retry') {
            pushLog({
              timestamp: ts,
              level: 'warning',
              message: `模型调用失败，正在重试${evt.error_message ? `: ${evt.error_message}` : ''}`,
              taskId,
            })
          }
        })
      }

      // Sub-executor events must not overwrite the parent job's status,
      // percent or result; their progress lives inside the tagged log group.
      if (!isSubagentEvent) {
        setStatus(
          jid,
          status === 'completed'
            ? 'completed'
            : status === 'failed' || status === 'cancelled'
            ? 'failed'
            : status === 'awaiting_human'
            ? 'running'
            : 'running',
          data.progress_pct,
          data.current_phase || null
        )

        if (data.result) {
          setResult(jid, data.result)
        }
      }

      if (data.error_message) {
        pushLog({
          timestamp: new Date().toISOString(),
          level: 'error',
          message: data.error_message,
          taskId: data.active_task_id || undefined,
        })
      }

      if (isTerminal) {
        if (actor) {
          // A sub-executor finished: drop a terminal marker into its log
          // group so the panel can pin a final status badge on it. The parent
          // job keeps running — do not touch the SSE connection or the
          // top-level status here.
          pushLog({
            timestamp: new Date().toISOString(),
            level: status === 'completed' ? 'success' : 'error',
            message:
              status === 'completed'
                ? t('executionLog.subagentCompleted', { actor })
                : t('executionLog.subagentFailed', { actor }),
            subStatus: status === 'completed' ? 'completed' : 'failed',
          })
          return false
        }
        eventSourceRef.current?.close()
        if (pollTimerRef.current) {
          clearInterval(pollTimerRef.current)
          pollTimerRef.current = null
        }
        setConnected(jid, false)
        pushLog({
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
          const res = await executionApi.getTrace(jid)
          const trace = res.data
          const resultNode =
            trace.nodes?.find((n: any) => n.outputs?.result?.success !== undefined) ||
            trace.nodes?.find((n: any) => n.outputs?.success !== undefined) ||
            trace.nodes?.find((n: any) => n.outputs?.result?.status === 'failure')
          const outputs = resultNode?.outputs
          if (outputs) {
            if (outputs.result) {
              setResult(jid, outputs.result)
              return
            } else if (outputs.success !== undefined) {
              setResult(jid, outputs)
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
      const jobSessionId = useExecutionStore.getState().jobs[jid]?.sessionId
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
      const url = executionApi.eventsUrl(jid)
      const es = new EventSource(url)
      eventSourceRef.current = es

      es.onopen = () => {
        retryCountRef.current = 0
        setConnected(jid, true)
        addLog(jid, {
          timestamp: new Date().toISOString(),
          level: 'info',
          message: t('executionLog.running') + ` (${jid.slice(0, 8)})`,
        })
      }

      es.addEventListener('state', (event) => {
        try {
          const data = JSON.parse(event.data)
          // Workflow progress payloads share the state channel: the backend
          // emits them as full ExecutionState dicts with extra top-level keys
          // (type/event/domain/phases/phase). Feed the workflow handler first,
          // then let the regular state processing apply to the same payload.
          if (isWorkflowProgressPayload(data)) {
            applyWorkflowProgress(data)
            if (typeof data.status !== 'string') return
          }
          applyPayload(data as ExecutionStatePayload)
        } catch {
          addLog(jid, {
            timestamp: new Date().toISOString(),
            level: 'info',
            message: event.data,
          })
        }
      })

      // Dedicated channel for domain-pipeline progress (skeleton + phases).
      es.addEventListener('progress', (event) => {
        try {
          const data = JSON.parse(event.data)
          if (isWorkflowProgressPayload(data)) {
            applyWorkflowProgress(data)
          }
        } catch {
          // Ignore malformed progress events; the state stream is unaffected.
        }
      })

      es.onerror = () => {
        setConnected(jid, false)
        es.close()

        if (retryCountRef.current < MAX_RECONNECT_RETRIES) {
          const delay = RECONNECT_BASE_DELAY_MS * 2 ** retryCountRef.current
          retryCountRef.current += 1
          addLog(jid, {
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
          addLog(jid, {
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
      addLog(jid, {
        timestamp: new Date().toISOString(),
        level: 'warning',
        message: 'SSE unavailable; falling back to polling.',
      })

      async function poll() {
        try {
          const res = await executionApi.getTrace(jid)
          const trace = res.data
          const status = String(trace.status || 'running').toLowerCase()
          const isTerminal = status === 'completed' || status === 'failed' || status === 'cancelled'

          setStatus(
            jid,
            status === 'completed'
              ? 'completed'
              : status === 'failed' || status === 'cancelled'
              ? 'failed'
              : 'running',
            isTerminal ? 100 : 50
          )

          if (trace.error_message) {
            addLog(jid, {
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
              setResult(jid, outputs.result)
            } else if (outputs.success !== undefined) {
              setResult(jid, outputs)
            }
          }

          if (isTerminal) {
            if (pollTimerRef.current) {
              clearInterval(pollTimerRef.current)
              pollTimerRef.current = null
            }
            setConnected(jid, false)
            addLog(jid, {
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
  }, [jobId, addLog, setConnected, setStatus, setResult, setWorkflowSkeleton, setPhaseState, setTaskTree, updateTaskStatus, setProgress, t])
}
