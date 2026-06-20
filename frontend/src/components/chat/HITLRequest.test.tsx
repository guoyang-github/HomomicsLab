import '@testing-library/jest-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { HITLRequest } from './HITLRequest'
import * as api from '@/services/api'

vi.mock('@/services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/api')>()
  return {
    ...actual,
    chatApi: {
      ...actual.chatApi,
      respondToHITL: vi.fn().mockResolvedValue({}),
    },
  }
})

describe('HITLRequest', () => {
  const checkpoint = {
    id: 'chk-1',
    trigger_reason: 'high_risk',
    context_summary: 'Risky step needs confirmation',
    options: [
      { id: 'proceed', label: 'Proceed', description: 'Continue anyway' },
      { id: 'abort', label: 'Abort' },
    ],
    default_option: { id: 'proceed', label: 'Proceed' },
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders options and remember toggle', () => {
    render(<HITLRequest checkpoint={checkpoint} taskId="task-1" />)
    expect(screen.getByRole('radio', { name: /Proceed/ })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Abort' })).toBeInTheDocument()
    expect(screen.getByLabelText(/Remember my choice/)).toBeInTheDocument()
  })

  it('submits with remember flag when checked', async () => {
    render(<HITLRequest checkpoint={checkpoint} taskId="task-1" />)

    fireEvent.click(screen.getByLabelText(/Remember my choice/))
    fireEvent.click(screen.getByRole('button', { name: /Confirm/ }))

    await waitFor(() => expect(api.chatApi.respondToHITL).toHaveBeenCalled())
    const callArgs = (api.chatApi.respondToHITL as ReturnType<typeof vi.fn>).mock.calls[0][0]
    expect(callArgs.remember).toBe(true)
  })
})
