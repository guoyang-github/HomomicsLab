import '@testing-library/jest-dom'
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ResultPreview } from './ResultPreview'

describe('ResultPreview', () => {
  const baseCall = {
    tool_name: 'scanpy_qc',
    inputs: { min_genes: 200 },
    success: true,
    output_summary: 'QC finished: 2700 cells kept',
  }

  it('renders a collapsed one-line summary per tool call', () => {
    render(<ResultPreview content={{ tool_calls: [baseCall] }} />)
    expect(screen.getByText('scanpy_qc')).toBeInTheDocument()
    expect(screen.getByText('QC finished: 2700 cells kept')).toBeInTheDocument()
    // Details are hidden until expanded.
    expect(screen.queryByText('Inputs')).not.toBeInTheDocument()
  })

  it('expands to show inputs and output on click', () => {
    render(<ResultPreview content={{ tool_calls: [baseCall] }} />)
    fireEvent.click(screen.getByRole('button', { name: /scanpy_qc/ }))
    expect(screen.getByText('Inputs')).toBeInTheDocument()
    expect(screen.getByText('Output')).toBeInTheDocument()
    expect(screen.getByText(/"min_genes": 200/)).toBeInTheDocument()
  })

  it('shows the running label for in-flight tool calls', () => {
    render(
      <ResultPreview
        content={{
          tool_calls: [{ ...baseCall, success: false, status: 'running' }],
        }}
      />
    )
    expect(screen.getByText('Running')).toBeInTheDocument()
  })

  it('truncates long output and reveals it via the toggle', () => {
    const longOutput = 'x'.repeat(600)
    render(
      <ResultPreview
        content={{ tool_calls: [{ ...baseCall, output_summary: longOutput }] }}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /scanpy_qc/ }))
    expect(screen.getByText('Show full output')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Show full output'))
    expect(screen.getByText(longOutput)).toBeInTheDocument()
    expect(screen.getByText('Collapse output')).toBeInTheDocument()
  })
})
