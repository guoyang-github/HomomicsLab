import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { usePresence } from './collab'

class MockWebSocket {
  static instances: MockWebSocket[] = []
  url: string
  readyState: number = WebSocket.CONNECTING
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  sent: string[] = []

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  send(data: string) {
    this.sent.push(data)
  }

  close() {
    this.readyState = WebSocket.CLOSED
    if (this.onclose) this.onclose()
  }

  // Test helpers
  open() {
    this.readyState = WebSocket.OPEN
    if (this.onopen) this.onopen()
  }

  receive(data: unknown) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }))
    }
  }
}

describe('usePresence', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    vi.stubGlobal('WebSocket', MockWebSocket)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('connects and tracks other users', async () => {
    const { result } = renderHook(() => usePresence('proj_1', 'alice'))

    await waitFor(() => expect(MockWebSocket.instances.length).toBe(1))
    const ws = MockWebSocket.instances[0]

    act(() => ws.open())
    expect(result.current.isConnected).toBe(true)

    act(() =>
      ws.receive({
        type: 'user_joined',
        user: { user_id: 'bob', cursor_x: 10, cursor_y: 20, editing: false, color: '#3b82f6' },
      })
    )

    await waitFor(() => expect(result.current.users).toHaveLength(1))
    expect(result.current.users[0].user_id).toBe('bob')
  })

  it('does not connect when projectId is null', async () => {
    renderHook(() => usePresence(null, 'alice'))
    expect(MockWebSocket.instances.length).toBe(0)
  })

  it('sends cursor positions', async () => {
    const { result } = renderHook(() => usePresence('proj_1', 'alice'))
    await waitFor(() => expect(MockWebSocket.instances.length).toBe(1))
    const ws = MockWebSocket.instances[0]
    act(() => ws.open())

    act(() => result.current.sendCursor(100, 200))
    expect(ws.sent).toContainEqual(JSON.stringify({ type: 'cursor', cursor_x: 100, cursor_y: 200 }))
  })
})
