import '@testing-library/jest-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { FigureWorkbench } from './FigureWorkbench'
import * as projectStore from '@/stores/projectStore'
import * as api from '@/services/api'

vi.mock('@/stores/projectStore', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/stores/projectStore')>()
  return {
    ...actual,
    useProjectStore: vi.fn(),
  }
})

vi.mock('@/services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/api')>()
  return {
    ...actual,
    fileApi: {
      ...actual.fileApi,
      uploadFile: vi.fn(),
    },
    vizApi: {
      ...actual.vizApi,
      createSession: vi.fn(),
      render: vi.fn(),
      listFigures: vi.fn(),
    },
  }
})

describe('FigureWorkbench', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(projectStore.useProjectStore as unknown as ReturnType<typeof vi.fn>).mockImplementation((selector: (state: any) => any) =>
      selector({ currentProjectId: 'proj-1' })
    )
  })

  it('renders workbench and render button', () => {
    render(<FigureWorkbench />)
    expect(screen.getByText(/Figure Workbench/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Create Session/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Render Figure/i })).toBeInTheDocument()
  })

  it('creates a session when source filename is provided', async () => {
    const createSessionMock = api.vizApi.createSession as unknown as ReturnType<typeof vi.fn>
    createSessionMock.mockResolvedValue({
      data: {
        session_id: 'sess-1',
        success: true,
        outputs: { data_id: 'data-1', table_type: 'column' },
        interpretation: 'Detected column table',
      },
    })

    render(<FigureWorkbench />)
    const sourceInput = screen.getByPlaceholderText(/Source filename in project/i)
    fireEvent.change(sourceInput, { target: { value: 'data.csv' } })
    fireEvent.click(screen.getByRole('button', { name: /Create Session/i }))

    await waitFor(() => expect(createSessionMock).toHaveBeenCalledWith({
      project_id: 'proj-1',
      source_filename: 'data.csv',
      table_type_hint: null,
    }))
    expect(await screen.findByText(/Detected column table/i)).toBeInTheDocument()
  })

  it('calls full_pipeline render when render button is clicked after session exists', async () => {
    const createSessionMock = api.vizApi.createSession as unknown as ReturnType<typeof vi.fn>
    createSessionMock.mockResolvedValue({
      data: {
        session_id: 'sess-1',
        success: true,
        outputs: { data_id: 'data-1', table_type: 'column' },
        interpretation: 'Detected column table',
      },
    })

    const renderMock = api.vizApi.render as unknown as ReturnType<typeof vi.fn>
    renderMock.mockResolvedValue({
      data: {
        success: true,
        outputs: { figure_id: 'fig-1', formats: { png: 'outputs/fig-1/fig-1.png' } },
        artifacts: [{ type: 'output', path: 'outputs/fig-1/fig-1.png', mime: 'image/png' }],
        interpretation: 'Rendered fig-1',
      },
    })

    render(<FigureWorkbench />)
    fireEvent.change(screen.getByPlaceholderText(/Source filename in project/i), { target: { value: 'data.csv' } })
    fireEvent.click(screen.getByRole('button', { name: /Create Session/i }))
    await waitFor(() => expect(createSessionMock).toHaveBeenCalled())

    fireEvent.click(screen.getByRole('button', { name: /Render Figure/i }))
    await waitFor(() => expect(renderMock).toHaveBeenCalledWith('sess-1', expect.objectContaining({
      action: 'full_pipeline',
      params: expect.objectContaining({
        source: 'data.csv',
        plot_type: 'box',
        theme: 'nature',
        test_name: 'one_way_anova',
      }),
    })))
  })
})
