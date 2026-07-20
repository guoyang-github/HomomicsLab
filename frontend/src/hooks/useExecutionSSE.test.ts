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

  it('restores the workflow skeleton from the trace on terminal state', async () => {
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
      data: {
        nodes: [
          { node_id: 'root', node_type: 'plan', name: 'job', status: 'completed', metadata: {} },
          {
            node_id: 'skel',
            node_type: 'plan',
            name: 'workflow_skeleton:single-cell-transcriptomics',
            metadata: {
              event: 'workflow_skeleton',
              domain: 'single-cell-transcriptomics',
              phases: [{ phase_type: 'qc', name: 'Quality Control', skipped: false }],
              task_id: 'task_1',
            },
          },
          {
            node_id: 'p1',
            node_type: 'phase',
            name: 'phase:qc:done',
            metadata: { event: 'phase', phase: 'qc', status: 'done', params: { min_genes: 200 }, task_id: 'task_1' },
          },
        ],
      },
    } as any)

    renderHook(() => useExecutionSSE('job_1'))
    const es = MockEventSource.instances[0]

    act(() => {
      es.emit('state', { job_id: 'job_1', status: 'completed', progress_pct: 100 })
    })

    await waitFor(() =>
      expect(useExecutionStore.getState().jobs['job_1'].workflowSkeleton?.domain).toBe(
        'single-cell-transcriptomics'
      )
    )
    const job = useExecutionStore.getState().jobs['job_1']
    expect(job.phaseStates['qc'].status).toBe('completed')
    expect(job.phaseStates['qc'].params).toEqual({ min_genes: 200 })
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

  it('stores the workflow skeleton and phase progress from progress events', () => {
    useExecutionStore.getState().startJob('job_1', 'sess_1')
    renderHook(() => useExecutionSSE('job_1'))
    const es = MockEventSource.instances[0]

    act(() =>
      es.emit('progress', {
        type: 'progress',
        event: 'workflow_skeleton',
        job_id: 'job_1',
        session_id: 'sess_1',
        domain: 'single-cell-transcriptomics',
        phases: [
          { phase_type: 'qc', name: 'Quality Control', skipped: false },
          { phase_type: 'normalization', name: 'Normalization', skipped: false },
        ],
      })
    )

    let job = useExecutionStore.getState().jobs['job_1']
    expect(job.workflowSkeleton?.domain).toBe('single-cell-transcriptomics')
    expect(job.workflowSkeleton?.phases).toHaveLength(2)

    act(() => es.emit('progress', { type: 'progress', event: 'phase', job_id: 'job_1', phase: 'qc', status: 'start' }))
    act(() =>
      es.emit('progress', {
        type: 'progress',
        event: 'phase',
        job_id: 'job_1',
        phase: 'qc',
        status: 'done',
        params: { min_genes: 200 },
      })
    )
    act(() => es.emit('progress', { type: 'progress', event: 'phase', job_id: 'job_1', phase: 'normalization', status: 'failed' }))

    job = useExecutionStore.getState().jobs['job_1']
    expect(job.phaseStates['qc'].status).toBe('completed')
    expect(job.phaseStates['qc'].params).toEqual({ min_genes: 200 })
    expect(job.phaseStates['normalization'].status).toBe('failed')
    // Progress events must not disturb the job-level status stream.
    expect(job.status).toBe('running')
  })

  it('tolerates workflow progress payloads arriving on the state channel', () => {
    useExecutionStore.getState().startJob('job_1', 'sess_1')
    renderHook(() => useExecutionSSE('job_1'))
    const es = MockEventSource.instances[0]

    // The backend emits workflow events as full ExecutionState dicts; both the
    // workflow store and the job-level status stream must be updated.
    act(() =>
      es.emit('state', {
        type: 'progress',
        event: 'workflow_skeleton',
        job_id: 'job_1',
        status: 'running',
        progress_pct: 5,
        current_phase: 'qc',
        domain: 'spatial-transcriptomics',
        phases: [{ phase_type: 'qc', name: 'QC' }],
      })
    )
    act(() =>
      es.emit('state', {
        type: 'progress',
        event: 'phase',
        job_id: 'job_1',
        status: 'running',
        progress_pct: 40,
        phase: 'qc',
        params: { min_genes: 200 },
      })
    )
    // A bare progress payload without an execution status must not crash the
    // state handler either.
    act(() => es.emit('state', { type: 'progress', event: 'phase', job_id: 'job_1', phase: 'qc', status: 'done' }))

    const job = useExecutionStore.getState().jobs['job_1']
    expect(job.workflowSkeleton?.domain).toBe('spatial-transcriptomics')
    expect(job.workflowSkeleton?.phases[0]).toEqual({ phase_type: 'qc', name: 'QC', skipped: false })
    expect(job.phaseStates['qc'].status).toBe('completed')
    expect(job.phaseStates['qc'].params).toEqual({ min_genes: 200 })
    expect(job.status).toBe('running')
    expect(job.percent).toBe(40)
  })

  it('drops malformed workflow progress payloads without breaking the stream', () => {
    useExecutionStore.getState().startJob('job_1', 'sess_1')
    renderHook(() => useExecutionSSE('job_1'))
    const es = MockEventSource.instances[0]

    act(() => es.emit('progress', { type: 'progress', event: 'workflow_skeleton', job_id: 'job_1', phases: [] }))
    act(() => es.emit('progress', { type: 'progress', event: 'phase', job_id: 'job_1', phase: 'qc' }))
    act(() => es.emit('progress', { type: 'progress', event: 'phase', job_id: 'job_1', status: 'start' }))
    act(() => es.emit('progress', 'not an object'))

    const job = useExecutionStore.getState().jobs['job_1']
    expect(job.workflowSkeleton).toBeNull()
    expect(job.phaseStates).toEqual({})

    // The regular state stream keeps working afterwards.
    act(() => es.emit('state', { job_id: 'job_1', status: 'running', progress_pct: 10 }))
    expect(useExecutionStore.getState().jobs['job_1'].percent).toBe(10)
  })

  it('renders chart_critique agent events as leveled log lines', () => {
    useExecutionStore.getState().startJob('job_1', 'sess_1')
    renderHook(() => useExecutionSSE('job_1'))
    const es = MockEventSource.instances[0]

    act(() =>
      es.emit('state', {
        job_id: 'job_1',
        status: 'running',
        progress_pct: 85,
        active_task_id: 't1',
        resource_usage: {
          agent_events: [
            {
              type: 'chart_critique',
              timestamp: 1700000000,
              tool: 'chart_critic',
              success: true,
              output: 'umap.png: ok=True severity=low issues=[] suggestion= source=vlm',
              artifacts: ['/tmp/umap.png'],
            },
            {
              type: 'chart_critique',
              timestamp: 1700000001,
              tool: 'chart_critic',
              success: false,
              output: "volcano.png: ok=False severity=high issues=['blank image'] suggestion=regenerate source=vlm",
              artifacts: ['/tmp/volcano.png'],
            },
            {
              type: 'chart_critique',
              timestamp: 1700000002,
              tool: 'chart_critic',
              success: false,
              output: "heat.png: ok=False severity=medium issues=['small fonts'] suggestion=enlarge source=vlm",
              artifacts: ['/tmp/heat.png'],
            },
          ],
        },
      })
    )

    const job = useExecutionStore.getState().jobs['job_1']
    const pass = job.logs.find((l) => l.message.includes('umap.png'))
    const high = job.logs.find((l) => l.message.includes('volcano.png'))
    const medium = job.logs.find((l) => l.message.includes('heat.png'))
    expect(pass?.level).toBe('success')
    expect(pass?.message).toContain('chart_critic')
    expect(pass?.taskId).toBe('t1')
    expect(high?.level).toBe('error')
    expect(high?.message).toContain('severity=high')
    expect(medium?.level).toBe('warning')
  })
})
