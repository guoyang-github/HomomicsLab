import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { useExecutionSSE } from './useExecutionSSE'
import { useExecutionStore } from '@/stores/executionStore'
import { useTaskStore } from '@/stores/taskStore'
import { useChatStore } from '@/stores/chatStore'
import { executionApi } from '@/services/api'

class MockEventSource {
  static instances: MockEventSource[] = []
  url: string
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  closed = false
  private listeners = new Map<string, (event: { data: string }) => void>()

  constructor(url: string) {
    this.url = url
    MockEventSource.instances.push(this)
  }

  addEventListener(type: string, cb: (event: { data: string }) => void) {
    this.listeners.set(type, cb)
  }

  close() {
    this.closed = true
  }

  emit(type: string, payload: unknown) {
    this.listeners.get(type)?.({ data: JSON.stringify(payload) })
  }
}

const originalLoadSessionMessages = useChatStore.getState().loadSessionMessages

describe('useExecutionSSE', () => {
  beforeEach(() => {
    MockEventSource.instances = []
    vi.stubGlobal('EventSource', MockEventSource)
    useExecutionStore.getState().reset()
    useTaskStore.getState().setTaskTree([])
    useChatStore.setState({
      messages: [],
      currentSessionId: 'sess_1',
      loadSessionMessages: originalLoadSessionMessages,
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('streams state events into the execution store', () => {
    useExecutionStore.getState().startJob('job_1', 'sess_1')
    renderHook(() => useExecutionSSE('job_1'))
    const es = MockEventSource.instances[0]
    expect(es.url).toContain('/execution/job_1/events')

    act(() => es.onopen?.())
    expect(useExecutionStore.getState().jobs['job_1'].isConnected).toBe(true)

    act(() =>
      es.emit('state', {
        job_id: 'job_1',
        status: 'running',
        progress_pct: 25,
        current_phase: 'qc',
        active_task_id: 't1',
        logs: ['hello world'],
      })
    )

    const job = useExecutionStore.getState().jobs['job_1']
    expect(job.status).toBe('running')
    expect(job.percent).toBe(25)
    expect(job.currentPhase).toBe('qc')
    expect(job.logs.some((l) => l.message === 'hello world')).toBe(true)
  })

  it('refreshes session messages and restores the result on terminal state', async () => {
    useExecutionStore.getState().restoreJob('job_1', 'sess_1')
    const loadSessionMessages = vi.fn().mockResolvedValue(undefined)
    useChatStore.setState({
      loadSessionMessages,
      currentSessionId: 'sess_1',
      messages: [
        {
          id: 'm_final',
          type: 'text',
          content: 'analysis done',
          sender: 'agent',
          timestamp: new Date().toISOString(),
        },
      ],
    })
    vi.spyOn(executionApi, 'getTrace').mockResolvedValue({
      data: { nodes: [{ node_id: 'n1', outputs: { result: { success: true } } }] },
    } as any)

    renderHook(() => useExecutionSSE('job_1'))
    const es = MockEventSource.instances[0]

    act(() => {
      es.emit('state', { job_id: 'job_1', status: 'completed', progress_pct: 100 })
    })

    await waitFor(() => expect(loadSessionMessages).toHaveBeenCalledWith('sess_1'))
    await waitFor(() => expect(useExecutionStore.getState().jobs['job_1'].result).toEqual({ success: true }))
    const job = useExecutionStore.getState().jobs['job_1']
    expect(job.status).toBe('completed')
    expect(job.isConnected).toBe(false)
    expect(es.closed).toBe(true)
    expect(job.logs.some((l) => l.level === 'success')).toBe(true)
  })

  it('tags subagent events without overwriting the parent job status', () => {
    useExecutionStore.getState().restoreJob('job_1', 'sess_1', [], 'running', 30, 'qc')
    renderHook(() => useExecutionSSE('job_1'))
    const es = MockEventSource.instances[0]

    act(() => {
      es.emit('state', {
        job_id: 'job_1',
        status: 'completed',
        progress_pct: 100,
        actor: 'subagent:celltypist',
        parent_id: 'task_1',
        logs: ['sub line'],
      })
    })

    const job = useExecutionStore.getState().jobs['job_1']
    // A sub-executor terminal event must not close the SSE connection or
    // overwrite the parent job's status / percent.
    expect(job.status).toBe('running')
    expect(job.percent).toBe(30)
    expect(es.closed).toBe(false)
    const subLog = job.logs.find((l) => l.message === 'sub line')
    expect(subLog?.actor).toBe('subagent:celltypist')
    expect(subLog?.parentId).toBe('task_1')
    expect(job.logs.some((l) => l.subStatus === 'completed')).toBe(true)
  })
})
