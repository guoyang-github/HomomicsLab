import '@testing-library/jest-dom'
import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MessageGroup } from './MessageGroup'
import { MessageList } from './MessageList'
import { useChatStore } from '@/stores/chatStore'
import type { ChatMessage } from '@/types/chat'
import type { TaskNode } from '@/types/tasks'

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

beforeAll(() => {
  // jsdom does not implement scrollIntoView; MessageList calls it on render.
  window.HTMLElement.prototype.scrollIntoView = vi.fn()
})

describe('MessageGroup', () => {
  beforeEach(() => {
    useChatStore.setState({ messages: [], currentSessionId: 'sess_1', currentProjectId: 'proj_1' })
  })

  it('keeps a status-only todo_list in the main flow without an Output section', () => {
    const messages = [
      makeMessage({
        id: 'a1',
        type: 'todo_list',
        content: {
          text: 'Running quality control and clustering steps',
          tasks: [makeTask('qc', 'running')],
        },
      }),
    ]
    render(<MessageGroup messages={messages} />)

    // The status text is rendered inline in the main message flow.
    expect(screen.getByText(/Running quality control/)).toBeInTheDocument()
    // Regression: a bare status/tasks card must not produce an empty Output box.
    expect(screen.queryByText('Output')).not.toBeInTheDocument()
  })

  it('moves a todo_list with artifacts into the Output section', () => {
    const messages = [
      makeMessage({
        id: 'a1',
        type: 'todo_list',
        content: {
          text: 'Analysis finished with one output file',
          status: 'completed',
          tasks: [makeTask('qc', 'completed')],
          artifacts: [
            { kind: 'file', name: 'result.csv', path: '/workspaces/proj_1/outputs/result.csv' },
          ],
        },
      }),
    ]
    render(<MessageGroup messages={messages} />)

    expect(screen.getByText('Output')).toBeInTheDocument()
    expect(screen.getByText('result.csv')).toBeInTheDocument()
  })
})

describe('MessageList grouping', () => {
  beforeEach(() => {
    useChatStore.setState({
      messages: [],
      currentSessionId: 'sess_1',
      currentProjectId: 'proj_1',
      messagesLoading: false,
      isTyping: false,
    })
  })

  it('aggregates consecutive same-sender messages into a single turn', () => {
    useChatStore.setState({
      messages: [
        makeMessage({ id: 'u1', sender: 'user', content: 'first question' }),
        makeMessage({ id: 'a1', sender: 'agent', content: 'answer part one' }),
        makeMessage({ id: 'a2', sender: 'agent', content: 'answer part two' }),
        makeMessage({ id: 'u2', sender: 'user', content: 'follow up' }),
      ],
    })
    render(<MessageList />)

    // Three turns: user / agent / user. Each group renders exactly one role label.
    expect(screen.getAllByText('You')).toHaveLength(2)
    expect(screen.getAllByText('Homomics Agent')).toHaveLength(1)
    // Both agent messages are rendered inside the single aggregated turn.
    expect(screen.getByText('answer part one')).toBeInTheDocument()
    expect(screen.getByText('answer part two')).toBeInTheDocument()
  })
})
