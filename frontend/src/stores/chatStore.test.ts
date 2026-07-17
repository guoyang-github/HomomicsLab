import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useChatStore } from './chatStore'
import { useTaskStore } from './taskStore'
import { usePlanStore } from './planStore'
import { useExecutionStore } from './executionStore'
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

  it('resets plan/execution/task stores when switching sessions', async () => {
    usePlanStore.getState().loadPlan(makePlan())
    useExecutionStore.getState().startJob('job_old', 'sess_old')
    useExecutionStore.getState().addLog({
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
    expect(exec.jobId).toBeNull()
    expect(exec.status).toBe('idle')
    expect(exec.logs).toEqual([])
    expect(exec.percent).toBe(0)
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
    // No running job in history: the execution store stays idle.
    expect(useExecutionStore.getState().jobId).toBeNull()
    expect(useExecutionStore.getState().status).toBe('idle')
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
    expect(exec.jobId).toBe('job_1')
    expect(exec.jobSessionId).toBe('sess_1')
    expect(exec.status).toBe('running')
    expect(exec.percent).toBe(40)
    expect(exec.currentPhase).toBe('clustering')
    expect(exec.logs.some((l) => l.message === 'trace line')).toBe(true)
  })
})
