import '@testing-library/jest-dom'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ExecutionLogPanel } from './ExecutionLogPanel'
import { useExecutionStore } from '@/stores/executionStore'
import { useChatStore } from '@/stores/chatStore'
import type { LogEntry } from '@/stores/executionStore'

// jsdom does not implement Element.scrollTo; the panel calls it on expand.
Element.prototype.scrollTo = vi.fn() as unknown as typeof Element.prototype.scrollTo

function seedLogs(logs: Array<Partial<LogEntry> & { message: string }>) {
  // The panel renders the active job of the current session.
  useChatStore.setState({ currentSessionId: 'sess_1' })
  useExecutionStore.setState({
    jobs: {
      job_1: {
        sessionId: 'sess_1',
        isConnected: false,
        status: 'running',
        percent: 0,
        currentPhase: null,
        result: null,
        updatedAt: Date.now(),
        logs: logs.map((partial, idx) => ({
          id: `log_${idx}`,
          timestamp: '2026-07-14T10:00:00.000Z',
          level: 'info',
          ...partial,
        })),
      },
    },
    activeJobIdBySession: { sess_1: 'job_1' },
  })
}

function expandPanel() {
  fireEvent.click(screen.getByTitle('Expand'))
}

describe('ExecutionLogPanel subagent grouping', () => {
  beforeEach(() => {
    useExecutionStore.getState().reset()
  })

  afterEach(() => {
    useExecutionStore.getState().reset()
  })

  it('renders untagged logs flat without any subagent group header', () => {
    seedLogs([{ message: 'plain top-level line' }])
    render(<ExecutionLogPanel />)
    expandPanel()

    expect(screen.getByText('plain top-level line')).toBeInTheDocument()
    expect(screen.queryByText(/subagent:/)).not.toBeInTheDocument()
  })

  it('shows a running subagent group expanded by default with its inner logs', () => {
    seedLogs([
      { message: 'parent started' },
      { message: 'loading model', actor: 'subagent:celltypist', parentId: 'task-1' },
      { message: 'parent still running' },
    ])
    render(<ExecutionLogPanel />)
    expandPanel()

    expect(screen.getByText('🔬 subagent: celltypist')).toBeInTheDocument()
    expect(screen.getByText('loading model')).toBeInTheDocument()
    expect(screen.getByText('parent started')).toBeInTheDocument()
    expect(screen.getByText('parent still running')).toBeInTheDocument()
  })

  it('collapses a running group when its header is clicked', () => {
    seedLogs([{ message: 'loading model', actor: 'subagent:celltypist', parentId: 'task-1' }])
    render(<ExecutionLogPanel />)
    expandPanel()

    const header = screen.getByRole('button', { name: /subagent: celltypist/ })
    expect(header).toHaveAttribute('aria-expanded', 'true')

    fireEvent.click(header)
    expect(header).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('loading model')).not.toBeInTheDocument()
  })

  it('collapses a finished group by default, keeps the final status badge, and expands on click', () => {
    seedLogs([
      { message: 'loading model', actor: 'subagent:celltypist', parentId: 'task-1' },
      {
        message: 'subagent:celltypist completed',
        level: 'success',
        actor: 'subagent:celltypist',
        parentId: 'task-1',
        subStatus: 'completed',
      },
    ])
    render(<ExecutionLogPanel />)
    expandPanel()

    const header = screen.getByRole('button', { name: /subagent: celltypist/ })
    expect(header).toHaveAttribute('aria-expanded', 'false')
    // Final status badge stays visible while collapsed.
    expect(screen.getByText('Completed')).toBeInTheDocument()
    expect(screen.queryByText('loading model')).not.toBeInTheDocument()

    fireEvent.click(header)
    expect(header).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('loading model')).toBeInTheDocument()
    // The terminal marker line is part of the group.
    expect(screen.getByText('subagent:celltypist completed')).toBeInTheDocument()
  })

  it('pins a Failed badge when the subagent ends with a failure marker', () => {
    seedLogs([
      {
        message: 'subagent:celltypist failed',
        level: 'error',
        actor: 'subagent:celltypist',
        parentId: 'task-1',
        subStatus: 'failed',
      },
    ])
    render(<ExecutionLogPanel />)
    expandPanel()

    expect(screen.getByText('Failed')).toBeInTheDocument()
  })
})
