import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the chat WebSocket stream service: captures the event handlers the
// store registers so tests can push tokens/agent events manually.
const h = vi.hoisted(() => ({
  events: null as null | {
    onToken?: (token: string) => void
    onDone?: () => void
    onReset?: () => void
    onAgentEvent?: (payload: Record<string, any>) => void
  },
  close: vi.fn(),
}))

vi.mock('@/services/chatStream', () => ({
  connectChatStream: vi.fn((_sessionId: string, events: any) => {
    h.events = events
    return { ready: Promise.resolve(true), close: h.close }
  }),
}))

import { useChatStore } from './chatStore'
import { useExecutionStore } from './executionStore'
import { useTaskStore } from './taskStore'
import { usePlanStore } from './planStore'
import { chatApi } from '@/services/api'
import type { ChatMessage } from '@/types/chat'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
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

function makeSendResponse(overrides: Record<string, unknown> = {}) {
  return {
    data: {
      response: 'final answer',
      task_tree: { tasks: [] },
      messages: [
        makeMessage({ id: 'msg_0', sender: 'user', content: '什么是 UMAP？' }),
        makeMessage({ id: 'msg_1', content: 'final answer' }),
      ],
      attachments: [],
      job_id: null,
      plan_id: null,
      plan: null,
      status: 'completed',
      ...overrides,
    },
  }
}

describe('chatStore.sendMessage streaming', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    h.events = null
    useChatStore.setState({
      sessions: [],
      messages: [],
      isTyping: false,
      currentSessionId: '',
      currentProjectId: 'default',
      messagesLoading: false,
      sessionRestoreAttempted: true,
    })
    useTaskStore.getState().setTaskTree([])
    usePlanStore.getState().discardDraft()
    useExecutionStore.getState().reset()
    // A non-generic name avoids the rename-on-first-message API call.
    useChatStore.getState().createSession('Streaming Session')
  })

  it('renders streamed tokens incrementally, then finalizes from the HTTP response', async () => {
    const send = deferred<any>()
    vi.spyOn(chatApi, 'sendMessage').mockImplementation(() => send.promise)

    const done = useChatStore.getState().sendMessage('什么是 UMAP？')
    await vi.waitFor(() => expect(h.events).toBeTruthy())

    h.events!.onToken!('UMAP')
    h.events!.onToken!(' 是一种降维方法')

    const mid = useChatStore.getState()
    expect(mid.isTyping).toBe(false)
    const placeholder = mid.messages.find((m) => m.id.startsWith('stream_'))
    expect(placeholder).toBeDefined()
    expect(placeholder?.content).toBe('UMAP 是一种降维方法')
    expect(placeholder?.sender).toBe('agent')
    expect(placeholder?.metadata?.streaming).toBe(true)

    send.resolve(makeSendResponse())
    await done

    const final = useChatStore.getState()
    // The placeholder is replaced wholesale by the authoritative list.
    expect(final.messages.map((m) => m.id)).toEqual(['msg_0', 'msg_1'])
    expect(final.isTyping).toBe(false)
    expect(h.close).toHaveBeenCalled()
  })

  it('drops partial tokens on a reset event', async () => {
    const send = deferred<any>()
    vi.spyOn(chatApi, 'sendMessage').mockImplementation(() => send.promise)

    const done = useChatStore.getState().sendMessage('什么是 UMAP？')
    await vi.waitFor(() => expect(h.events).toBeTruthy())

    h.events!.onToken!('partial')
    expect(useChatStore.getState().messages.some((m) => m.id.startsWith('stream_'))).toBe(true)

    h.events!.onReset!()
    expect(useChatStore.getState().messages.some((m) => m.id.startsWith('stream_'))).toBe(false)

    send.resolve(makeSendResponse())
    await done
    expect(useChatStore.getState().messages.map((m) => m.id)).toEqual(['msg_0', 'msg_1'])
  })

  it('stashes planning events and flushes them into the job execution logs', async () => {
    const send = deferred<any>()
    vi.spyOn(chatApi, 'sendMessage').mockImplementation(() => send.promise)

    const done = useChatStore.getState().sendMessage('run qc on my data')
    await vi.waitFor(() => expect(h.events).toBeTruthy())

    h.events!.onAgentEvent!({ type: 'planning', message: '正在分析数据并规划执行步骤…' })
    send.resolve(makeSendResponse({ job_id: 'job_1', status: 'queued' }))
    await done

    const job = useExecutionStore.getState().jobs['job_1']
    expect(job).toBeDefined()
    expect(job.logs.some((l) => l.message === '正在分析数据并规划执行步骤…')).toBe(true)
  })

  it('removes the streaming placeholder when the request fails', async () => {
    const send = deferred<any>()
    vi.spyOn(chatApi, 'sendMessage').mockImplementation(() => send.promise)

    const done = useChatStore.getState().sendMessage('什么是 UMAP？')
    await vi.waitFor(() => expect(h.events).toBeTruthy())

    h.events!.onToken!('partial')
    expect(useChatStore.getState().messages.some((m) => m.id.startsWith('stream_'))).toBe(true)

    send.reject({ response: { data: { detail: 'boom' } } })
    await done

    const state = useChatStore.getState()
    expect(state.messages.some((m) => m.id.startsWith('stream_'))).toBe(false)
    expect(state.messages.some((m) => m.type === 'error' && m.content === 'boom')).toBe(true)
    expect(state.isTyping).toBe(false)
    expect(h.close).toHaveBeenCalled()
  })
})
