import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DetailPanel } from './DetailPanel'
import { useExecutionStore } from '@/stores/executionStore'
import { useTaskStore } from '@/stores/taskStore'
import { useChatStore } from '@/stores/chatStore'

// PlanHistory fetches plan data on mount; keep the real module for everything
// else and stub only the API surface it touches.
vi.mock('@/services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/api')>()
  return {
    ...actual,
    planApi: {
      ...actual.planApi,
      listPlans: vi.fn().mockResolvedValue({ data: { plans: [] } }),
    },
  }
})

const skeleton = {
  domain: 'single-cell-transcriptomics',
  phases: [
    { phase_type: 'qc', name: 'Quality Control', skipped: false },
    { phase_type: 'normalization', name: 'Normalization', skipped: false },
  ],
}

beforeEach(() => {
  useExecutionStore.getState().reset()
  useTaskStore.getState().setTaskTree([])
  useTaskStore.getState().selectTask(null)
  useChatStore.setState({ currentSessionId: 'sess_1', messages: [] })
})

describe('DetailPanel skeleton phase fallback', () => {
  it('shows phase status and reported params as a key-value table', () => {
    useExecutionStore.getState().startJob('job_1', 'sess_1')
    useExecutionStore.getState().setWorkflowSkeleton('job_1', skeleton)
    useExecutionStore.getState().setPhaseState('job_1', 'qc', 'done', { min_genes: 200, method: 'lognorm' })
    // The phase node was clicked on the canvas; it is not in the task store.
    useTaskStore.getState().selectTask('qc')

    render(<DetailPanel />)

    const params = screen.getByTestId('phase-params')
    expect(params.textContent).toContain('min_genes')
    expect(params.textContent).toContain('200')
    expect(params.textContent).toContain('method')
    expect(params.textContent).toContain('lognorm')
    expect(screen.getByText('Completed')).toBeDefined()
  })

  it('shows an empty-params hint when the phase reported nothing', () => {
    useExecutionStore.getState().startJob('job_1', 'sess_1')
    useExecutionStore.getState().setWorkflowSkeleton('job_1', skeleton)
    useTaskStore.getState().selectTask('normalization')

    render(<DetailPanel />)

    expect(screen.queryByTestId('phase-params')).toBeNull()
    expect(screen.getByText('No parameters reported yet.')).toBeDefined()
    expect(screen.getByText('Pending')).toBeDefined()
  })

  it('keeps the plain hint when the selection matches neither a task nor a phase', () => {
    useTaskStore.getState().selectTask('ghost')

    render(<DetailPanel />)

    expect(screen.queryByTestId('phase-params')).toBeNull()
    expect(screen.getByText(/Click a node to view details/)).toBeDefined()
  })
})
