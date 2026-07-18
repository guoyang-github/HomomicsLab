import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { FlowCanvas } from './FlowCanvas'
import { useExecutionStore } from '@/stores/executionStore'
import { useTaskStore } from '@/stores/taskStore'
import { usePlanStore } from '@/stores/planStore'
import { useChatStore } from '@/stores/chatStore'
import type { TaskNode } from '@/types/tasks'

// React Flow needs layout APIs jsdom lacks; a light mock renders each node id
// and edge so the data-source switching logic stays testable.
vi.mock('reactflow', async () => {
  const React = await vi.importActual<typeof import('react')>('react')
  return {
    __esModule: true,
    default: ({ nodes, edges }: any) => (
      <div data-testid="reactflow">
        {nodes.map((n: any) => (
          <div key={n.id} data-testid={`flow-node-${n.id}`}>
            {`${n.data.name}|${n.data.status}`}
          </div>
        ))}
        {edges.map((e: any) => (
          <div key={e.id} data-testid={`flow-edge-${e.source}-${e.target}`} />
        ))}
      </div>
    ),
    Background: () => null,
    Controls: () => null,
    MiniMap: () => null,
    Handle: () => null,
    Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
    useNodesState: (initial: any) => {
      const [nodes, setNodes] = React.useState(initial)
      return [nodes, setNodes, vi.fn()]
    },
    useEdgesState: (initial: any) => {
      const [edges, setEdges] = React.useState(initial)
      return [edges, setEdges, vi.fn()]
    },
  }
})

function makeTask(overrides: Partial<TaskNode> = {}): TaskNode {
  return {
    id: 't1',
    name: 'Generic analysis',
    description: 'generic task',
    phase: 'analysis',
    status: 'pending',
    dependencies: [],
    skills_required: [],
    estimated_duration_minutes: 5,
    parameters: {},
    ...overrides,
  }
}

const skeleton = {
  domain: 'single-cell-transcriptomics',
  phases: [
    { phase_type: 'qc', name: 'Quality Control', skipped: false },
    { phase_type: 'doublet', name: 'Doublet Detection', skipped: true },
    { phase_type: 'normalization', name: 'Normalization', skipped: false },
  ],
}

beforeEach(() => {
  useExecutionStore.getState().reset()
  useTaskStore.getState().setTaskTree([])
  useTaskStore.getState().selectTask(null)
  usePlanStore.getState().discardDraft()
  useChatStore.setState({ currentSessionId: 'sess_1', messages: [] })
})

describe('FlowCanvas data source switching', () => {
  it('renders skeleton phases with live statuses when a skeleton exists', () => {
    useExecutionStore.getState().startJob('job_1', 'sess_1')
    useExecutionStore.getState().setWorkflowSkeleton('job_1', skeleton)
    useExecutionStore.getState().setPhaseState('job_1', 'qc', 'start')
    // Legacy tasks must be ignored while a skeleton drives the canvas.
    useTaskStore.getState().setTaskTree([makeTask()])

    render(<FlowCanvas />)

    expect(screen.getByTestId('flow-node-qc').textContent).toBe('Quality Control|running')
    expect(screen.getByTestId('flow-node-normalization').textContent).toBe('Normalization|pending')
    // Skipped phases and legacy tasks are not rendered.
    expect(screen.queryByTestId('flow-node-doublet')).toBeNull()
    expect(screen.queryByTestId('flow-node-t1')).toBeNull()
    // Serial dependency chain in array order.
    expect(screen.getByTestId('flow-edge-qc-normalization')).toBeDefined()
    expect(screen.getByText('Domain: single-cell-transcriptomics')).toBeDefined()
  })

  it('updates node status when a phase report arrives', () => {
    useExecutionStore.getState().startJob('job_1', 'sess_1')
    useExecutionStore.getState().setWorkflowSkeleton('job_1', skeleton)

    render(<FlowCanvas />)
    expect(screen.getByTestId('flow-node-qc').textContent).toBe('Quality Control|pending')

    act(() => {
      useExecutionStore.getState().setPhaseState('job_1', 'qc', 'done')
    })
    expect(screen.getByTestId('flow-node-qc').textContent).toBe('Quality Control|completed')
  })

  it('falls back to the task tree with display_subtasks expansion when no skeleton exists', () => {
    useTaskStore.getState().setTaskTree([
      makeTask({
        id: 't1',
        parameters: {
          display_subtasks: [
            { id: 'load', description: 'Load data' },
            { id: 'plot', description: 'Plot results' },
          ],
        },
      }),
    ])

    render(<FlowCanvas />)

    expect(screen.queryByTestId('flow-node-t1')).toBeNull()
    expect(screen.getByTestId('flow-node-t1::load').textContent).toContain('Load data')
    expect(screen.getByTestId('flow-node-t1::plot').textContent).toContain('Plot results')
    expect(screen.getByTestId('flow-edge-t1::load-t1::plot')).toBeDefined()
  })

  it('shows a friendly empty state instead of a blank canvas when there is no data', () => {
    render(<FlowCanvas />)
    expect(screen.getByTestId('workflow-empty')).toBeDefined()
    expect(screen.getByText('No workflow to display')).toBeDefined()
  })
})
