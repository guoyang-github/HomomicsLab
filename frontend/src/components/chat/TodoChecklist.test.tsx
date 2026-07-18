import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TodoChecklist } from './TodoChecklist'
import { useExecutionStore } from '@/stores/executionStore'
import { useTaskStore } from '@/stores/taskStore'
import { useChatStore } from '@/stores/chatStore'
import { usePlanStore } from '@/stores/planStore'
import type { TaskNode } from '@/types/tasks'
import type { ChatMessage } from '@/types/chat'

function makeTask(overrides: Partial<TaskNode> = {}): TaskNode {
  return {
    id: 't1',
    name: 'Analysis',
    description: 'Run analysis',
    phase: 'analysis',
    status: 'pending',
    dependencies: [],
    skills_required: [],
    estimated_duration_minutes: 5,
    parameters: {},
    ...overrides,
  }
}

function todoListMessage(domain?: string): ChatMessage {
  return {
    id: 'm1',
    type: 'todo_list',
    content: { text: 'Execution started', tasks: [makeTask()] },
    sender: 'agent',
    timestamp: new Date().toISOString(),
    ...(domain !== undefined ? { metadata: { domain } } : {}),
  }
}

const skeleton = {
  domain: 'single-cell-transcriptomics',
  phases: [{ phase_type: 'qc', name: 'Quality Control', skipped: false }],
}

beforeEach(() => {
  useExecutionStore.getState().reset()
  useTaskStore.getState().setTaskTree([makeTask()])
  useTaskStore.getState().selectTask(null)
  usePlanStore.getState().discardDraft()
  useChatStore.setState({ currentSessionId: 'sess_1', messages: [] })
})

describe('TodoChecklist workflow entry', () => {
  it('shows the workflow button for legacy task trees without a domain signal', async () => {
    render(<TodoChecklist />)
    expect(await screen.findByText('View full workflow')).toBeDefined()
  })

  it('shows the workflow button when the active job has a domain skeleton', async () => {
    useExecutionStore.getState().startJob('job_1', 'sess_1')
    useExecutionStore.getState().setWorkflowSkeleton('job_1', skeleton)

    render(<TodoChecklist />)
    expect(await screen.findByText('View full workflow')).toBeDefined()
  })

  it('shows the workflow button when the session carries a named domain hint', async () => {
    useChatStore.setState({ messages: [todoListMessage('genomics')] })

    render(<TodoChecklist />)
    expect(await screen.findByText('View full workflow')).toBeDefined()
  })

  it('hides the workflow button for generic tasks', async () => {
    useChatStore.setState({ messages: [todoListMessage('generic')] })

    render(<TodoChecklist />)
    // The checklist itself still renders…
    expect(await screen.findByTestId('todo-checklist')).toBeDefined()
    // …but the workflow entry stays hidden for non-domain tasks.
    expect(screen.queryByText('View full workflow')).toBeNull()
  })
})
