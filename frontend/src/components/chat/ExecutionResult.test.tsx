import '@testing-library/jest-dom'
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ExecutionResult } from './ExecutionResult'
import { useExecutionStore } from '@/stores/executionStore'

function seedJobResult(jobId: string, outputFile: string) {
  useExecutionStore.getState().startJob(jobId, `sess_${jobId}`)
  useExecutionStore.getState().setResult(jobId, { output_files: [outputFile] })
  useExecutionStore.getState().setStatus(jobId, 'completed')
}

beforeEach(() => {
  useExecutionStore.getState().reset()
})

describe('ExecutionResult store fallback', () => {
  it('reads the store result by the message job_id, not the latest job', () => {
    seedJobResult('job_old', '/workspaces/proj_1/outputs/old.csv')
    seedJobResult('job_new', '/workspaces/proj_1/outputs/new.csv')

    render(
      <ExecutionResult
        content={{ text: '', tasks: [], job_id: 'job_old', project_id: 'proj_1' }}
      />
    )

    // The older card shows its own job's outputs…
    expect(screen.getByText('old.csv')).toBeInTheDocument()
    // …and never the newer job's.
    expect(screen.queryByText('new.csv')).not.toBeInTheDocument()
  })

  it('does not leak a store result into a card whose job is unknown', () => {
    seedJobResult('job_new', '/workspaces/proj_1/outputs/new.csv')

    render(
      <ExecutionResult
        content={{ text: '', tasks: [], job_id: 'job_gone', project_id: 'proj_1' }}
      />
    )

    expect(screen.queryByText('new.csv')).not.toBeInTheDocument()
  })

  it('does not leak a store result into a card without a job_id', () => {
    seedJobResult('job_new', '/workspaces/proj_1/outputs/new.csv')

    render(<ExecutionResult content={{ text: '', tasks: [], project_id: 'proj_1' }} />)

    expect(screen.queryByText('new.csv')).not.toBeInTheDocument()
  })
})
