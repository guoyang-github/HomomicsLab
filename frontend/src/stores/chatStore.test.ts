import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useChatStore } from './chatStore'
import { useTaskStore } from './taskStore'
import { usePlanStore } from './planStore'
import { useExecutionStore, selectActiveJob } from './executionStore'
import { chatApi, executionApi } from '@/services/api'
import type { ChatMessage, PlanRequestContent } from '@/types/chat'
import type { TaskNode } from '@/types/tasks'

describe('chatStore', () => {
  it('should add a message', () => {
    const store = useChatStore.getState()
    store.addMessage({
      id: '1',
      type: 'text',
      content: 'hello',
      sender: 'user',
      timestamp: new Date().toISOString(),
    })

    expect(useChatStore.getState().messages).toHaveLength(1)
    expect(useChatStore.getState().messages[0].content).toBe('hello')
  })

  it('should set typing state', () => {
    useChatStore.getState().setIsTyping(true)
    expect(useChatStore.getState().isTyping).toBe(true)
  })

  it('should create session scoped to current project', () => {
    useChatStore.getState().setProjectId('proj_1')
    const id = useChatStore.getState().createSession('My Session')
    const session = useChatStore.getState().sessions.find((s) => s.id === id)
    expect(session).toBeDefined()
    expect(session?.projectId).toBe('proj_1')
    expect(useChatStore.getState().currentProjectId).toBe('proj_1')
  })

  it('should create session with explicit project id', () => {
    const id = useChatStore.getState().createSession('Explicit', 'proj_2')
    const session = useChatStore.getState().sessions.find((s) => s.id === id)
    expect(session?.projectId).toBe('proj_2')
  })
})

function makeTask(id: string, status: TaskNode['status'] = 'pending'): TaskNode {
  return {
    id,
    name: id,
    description: `${id} step`,
    phase: id,
    status,
    dependencies: [],
    skills_required: [],
    estimated_duration_minutes: 10,
    parameters: {},
  }
}

function makeMessage(partial: Partial<ChatMessage> & { id: string }): ChatMessage {
  return {
    type: 'text',
    content: '',
    sender: 'agent',
    timestamp: new Date().toISOString(),
    ...partial,
  }
}

function makePlan(): PlanRequestContent {
  return {
    plan_id: 'plan_1',
    response_text: 'test plan',
    plan: {
      plan_id: 'plan_1',
      status: 'pending_approval',
      is_fallback: false,
      intent_analysis_type: 'single_cell',
      phases: [
        { phase_type: 'qc', description: 'Quality control', required: true, readonly: false, parameters: {} },
      ],
      version: 1,
    },
  }
}

describe('chatStore.selectSession', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    useChatStore.setState({
      sessions: [],
      messages: [],
      isTyping: false,
      currentSessionId: '',
      currentProjectId: 'default',
      messagesLoading: false,
    })
    useTaskStore.getState().setTaskTree([])
    useTaskStore.getState().setProgress({
      total: 0,
      pending: 0,
      running: 0,
      completed: 0,
      failed: 0,
      awaiting_human: 0,
      percent: 0,
    })
    usePlanStore.getState().discardDraft()
    useExecutionStore.getState().reset()
  })

  it('clears plan/task stores and the execution view for the new session, retaining other job data', async () => {
    usePlanStore.getState().loadPlan(makePlan())
    useExecutionStore.getState().startJob('job_old', 'sess_old')
    useExecutionStore.getState().addLog('job_old', {
      timestamp: new Date().toISOString(),
      level: 'info',
      message: 'old log',
    })
    useTaskStore.getState().setTaskTree([makeTask('qc', 'running')])
    vi.spyOn(chatApi, 'getMessages').mockResolvedValue({ data: [] } as any)

    await useChatStore.getState().selectSession('sess_new')

    expect(useChatStore.getState().currentSessionId).toBe('sess_new')
    expect(usePlanStore.getState().draftPlan).toBeNull()
    expect(usePlanStore.getState().viewMode).toBeNull()
    const exec = useExecutionStore.getState()
    // The new session shows no job…
    expect(selectActiveJob(exec, 'sess_new')).toBeNull()
    // …but the previous session's job runtime is retained in memory.
    expect(exec.activeJobIdBySession['sess_old']).toBe('job_old')
    expect(exec.jobs['job_old'].status).toBe('running')
    expect(exec.jobs['job_old'].logs.map((l) => l.message)).toEqual(['old log'])
    expect(useTaskStore.getState().tasks).toEqual([])
    expect(useTaskStore.getState().progress.total).toBe(0)
  })

  it('rebuilds the task tree from a persisted todo_list message', async () => {
    const messages = [
      makeMessage({ id: 'm1', sender: 'user', content: 'run qc' }),
      makeMessage({
        id: 'm2',
        type: 'todo_list',
        content: {
          text: 'Execution plan',
          tasks: [makeTask('qc', 'completed'), makeTask('clustering', 'pending')],
        },
      }),
    ]
    vi.spyOn(chatApi, 'getMessages').mockResolvedValue({ data: messages } as any)

    await useChatStore.getState().selectSession('sess_1')

    expect(useTaskStore.getState().tasks.map((t) => t.id)).toEqual(['qc', 'clustering'])
    const progress = useTaskStore.getState().progress
    expect(progress.total).toBe(2)
    expect(progress.completed).toBe(1)
    expect(progress.percent).toBe(50)
    // No running job in history: the session has no active job.
    expect(selectActiveJob(useExecutionStore.getState(), 'sess_1')).toBeNull()
  })

  it('normalizes all tasks to the terminal status of a finished todo_list', async () => {
    const messages = [
      makeMessage({
        id: 'm1',
        type: 'todo_list',
        content: {
          text: 'done',
          status: 'completed',
          tasks: [makeTask('qc', 'running'), makeTask('clustering', 'pending')],
        },
      }),
    ]
    vi.spyOn(chatApi, 'getMessages').mockResolvedValue({ data: messages } as any)

    await useChatStore.getState().selectSession('sess_1')

    expect(useTaskStore.getState().tasks.every((t) => t.status === 'completed')).toBe(true)
  })

  it('recovers a running job via live status and trace', async () => {
    const messages = [
      makeMessage({
        id: 'm1',
        type: 'todo_list',
        content: {
          text: 'running',
          status: 'running',
          job_id: 'job_1',
          tasks: [makeTask('qc', 'running')],
        },
      }),
    ]
    vi.spyOn(chatApi, 'getMessages').mockResolvedValue({ data: messages } as any)
    const getStatus = vi.spyOn(executionApi, 'getStatus').mockResolvedValue({
      data: {
        latest_state: {
          status: 'running',
          progress_pct: 40,
          current_phase: 'clustering',
          tasks: [makeTask('qc', 'completed'), makeTask('clustering', 'running')],
          logs: ['live line'],
        },
      },
    } as any)
    vi.spyOn(executionApi, 'getTrace').mockResolvedValue({
      data: {
        nodes: [
          {
            node_id: 'qc',
            name: 'QC',
            status: 'completed',
            started_at: '2024-01-01T00:00:00Z',
            logs: ['trace line'],
          },
        ],
      },
    } as any)

    await useChatStore.getState().selectSession('sess_1')

    expect(getStatus).toHaveBeenCalledWith('job_1')
    // Live tasks from getStatus win over the persisted TODO card.
    expect(useTaskStore.getState().tasks.map((t) => t.id)).toEqual(['qc', 'clustering'])
    const exec = useExecutionStore.getState()
    expect(exec.activeJobIdBySession['sess_1']).toBe('job_1')
    const job = exec.jobs['job_1']
    expect(job.sessionId).toBe('sess_1')
    expect(job.status).toBe('running')
    expect(job.percent).toBe(40)
    expect(job.currentPhase).toBe('clustering')
    expect(job.logs.some((l) => l.message === 'trace line')).toBe(true)
  })

  it('retains a running job view when switching sessions away and back', async () => {
    const messagesA = [
      makeMessage({
        id: 'm1',
        type: 'todo_list',
        content: {
          text: 'running',
          status: 'running',
          job_id: 'job_a',
          tasks: [makeTask('qc', 'running')],
        },
      }),
    ]
    vi.spyOn(chatApi, 'getMessages').mockImplementation(async (id: string) => {
      return { data: id === 'sess_a' ? messagesA : [] } as any
    })
    vi.spyOn(executionApi, 'getStatus').mockResolvedValue({
      data: { latest_state: { status: 'running', progress_pct: 40, current_phase: 'qc' } },
    } as any)
    vi.spyOn(executionApi, 'getTrace').mockResolvedValue({ data: { nodes: [] } } as any)

    // Session A starts showing job_a; a live SSE log lands in memory.
    await useChatStore.getState().selectSession('sess_a')
    expect(useExecutionStore.getState().activeJobIdBySession['sess_a']).toBe('job_a')
    useExecutionStore.getState().addLog('job_a', {
      timestamp: new Date().toISOString(),
      level: 'stdout',
      message: 'live line A',
    })

    // Switch to session B: job_a's runtime stays in the store.
    await useChatStore.getState().selectSession('sess_b')
    let exec = useExecutionStore.getState()
    expect(selectActiveJob(exec, 'sess_b')).toBeNull()
    expect(exec.jobs['job_a'].logs.some((l) => l.message === 'live line A')).toBe(true)

    // Switch back to A: the pointer is intact, and restoreJob refreshes the
    // status without clobbering the in-memory log buffer.
    await useChatStore.getState().selectSession('sess_a')
    exec = useExecutionStore.getState()
    expect(exec.activeJobIdBySession['sess_a']).toBe('job_a')
    const job = exec.jobs['job_a']
    expect(job.status).toBe('running')
    expect(job.percent).toBe(40)
    expect(job.logs.some((l) => l.message === 'live line A')).toBe(true)
  })

  it('restores the workflow skeleton and phase states from trace nodes', async () => {
    const messages = [
      makeMessage({
        id: 'm1',
        type: 'todo_list',
        content: {
          text: 'done',
          status: 'completed',
          job_id: 'job_1',
          tasks: [makeTask('qc', 'completed')],
        },
      }),
    ]
    vi.spyOn(chatApi, 'getMessages').mockResolvedValue({ data: messages } as any)
    vi.spyOn(executionApi, 'getStatus').mockResolvedValue({
      data: { latest_state: { status: 'completed', progress_pct: 100 } },
    } as any)
    vi.spyOn(executionApi, 'getTrace').mockResolvedValue({
      data: {
        nodes: [
          { node_id: 'root', node_type: 'plan', name: 'job', status: 'completed', metadata: {} },
          {
            node_id: 'skel',
            node_type: 'plan',
            name: 'workflow_skeleton:single-cell-transcriptomics',
            status: 'running',
            metadata: {
              event: 'workflow_skeleton',
              domain: 'single-cell-transcriptomics',
              phases: [
                { phase_type: 'qc', name: 'Quality Control', skipped: false },
                { phase_type: 'normalization', name: 'Normalization', skipped: false },
              ],
              task_id: 'task_1',
            },
          },
          {
            node_id: 'p1',
            node_type: 'phase',
            name: 'phase:qc:done',
            status: 'running',
            metadata: { event: 'phase', phase: 'qc', status: 'done', params: { min_genes: 200 }, task_id: 'task_1' },
          },
        ],
      },
    } as any)

    await useChatStore.getState().selectSession('sess_1')

    const job = useExecutionStore.getState().jobs['job_1']
    expect(job.workflowSkeleton?.domain).toBe('single-cell-transcriptomics')
    expect(job.workflowSkeleton?.phases).toHaveLength(2)
    expect(job.phaseStates['qc'].status).toBe('completed')
    expect(job.phaseStates['qc'].params).toEqual({ min_genes: 200 })
  })

  it('keeps the live in-memory skeleton when switching sessions back', async () => {
    const messagesA = [
      makeMessage({
        id: 'm1',
        type: 'todo_list',
        content: {
          text: 'running',
          status: 'running',
          job_id: 'job_a',
          tasks: [makeTask('qc', 'running')],
        },
      }),
    ]
    vi.spyOn(chatApi, 'getMessages').mockImplementation(async (id: string) => {
      return { data: id === 'sess_a' ? messagesA : [] } as any
    })
    vi.spyOn(executionApi, 'getStatus').mockResolvedValue({
      data: { latest_state: { status: 'running', progress_pct: 40, current_phase: 'qc' } },
    } as any)
    // The trace still holds the older skeleton mirror; the live one must win.
    vi.spyOn(executionApi, 'getTrace').mockResolvedValue({
      data: {
        nodes: [
          {
            node_id: 'skel',
            node_type: 'plan',
            name: 'workflow_skeleton:genomics',
            metadata: {
              event: 'workflow_skeleton',
              domain: 'genomics',
              phases: [{ phase_type: 'qc', name: 'Trace QC', skipped: false }],
              task_id: 'task_1',
            },
          },
        ],
      },
    } as any)

    const liveSkeleton = {
      domain: 'single-cell-transcriptomics',
      phases: [{ phase_type: 'qc', name: 'Live QC', skipped: false }],
    }

    await useChatStore.getState().selectSession('sess_a')
    // A live SSE skeleton event lands after the trace restore.
    useExecutionStore.getState().setWorkflowSkeleton('job_a', liveSkeleton)
    useExecutionStore.getState().setPhaseState('job_a', 'qc', 'start')

    await useChatStore.getState().selectSession('sess_b')
    await useChatStore.getState().selectSession('sess_a')

    const job = useExecutionStore.getState().jobs['job_a']
    expect(job.workflowSkeleton).toEqual(liveSkeleton)
    expect(job.phaseStates['qc'].status).toBe('running')
  })
})
