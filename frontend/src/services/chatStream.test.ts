import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { connectChatStream } from './chatStream'

class MockWebSocket {
  static instances: MockWebSocket[] = []
  static OPEN = 1
  readyState = 0
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  sent: string[] = []
  url: string

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  send(data: string) {
    this.sent.push(data)
  }

  close() {
    this.readyState = 3
  }

  // Test helpers
  emitOpen() {
    this.readyState = 1
    this.onopen?.()
  }

  emitMessage(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) })
  }

  emitError() {
    this.onerror?.()
  }
}

describe('chatStream', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    vi.stubGlobal('WebSocket', MockWebSocket)
    // Reset the failure-cooldown module state between tests by re-importing.
    vi.resetModules()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  async function freshConnect(...args: Parameters<typeof connectChatStream>) {
    const mod = await import('./chatStream')
    return mod.connectChatStream(...args)
  }

  it('builds the session WS url under /api/chat/ws and resolves ready on open', async () => {
    const conn = await freshConnect('sess 1', {})
    const ws = MockWebSocket.instances[0]
    expect(ws.url).toContain('/api/chat/ws/sess%201')
    ws.emitOpen()
    await expect(conn.ready).resolves.toBe(true)
    conn.close()
  })

  it('dispatches token frames to onToken/onDone', async () => {
    const tokens: string[] = []
    let done = false
    const conn = await freshConnect('sess_1', {
      onToken: (t) => tokens.push(t),
      onDone: () => {
        done = true
      },
    })
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()
    await conn.ready

    ws.emitMessage({ type: 'token', token: 'Hel' })
    ws.emitMessage({ type: 'token', token: 'lo' })
    ws.emitMessage({ type: 'token', done: true })

    expect(tokens).toEqual(['Hel', 'lo'])
    expect(done).toBe(true)
    conn.close()
  })

  it('dispatches reset frames to onReset and agent_event frames to onAgentEvent', async () => {
    let resets = 0
    const payloads: Record<string, unknown>[] = []
    const conn = await freshConnect('sess_1', {
      onReset: () => {
        resets += 1
      },
      onAgentEvent: (p) => payloads.push(p),
    })
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()
    await conn.ready

    ws.emitMessage({ type: 'token', reset: true })
    ws.emitMessage({ type: 'agent_event', payload: { type: 'planning', message: '规划中' } })

    expect(resets).toBe(1)
    expect(payloads).toEqual([{ type: 'planning', message: '规划中' }])
    conn.close()
  })

  it('resolves ready=false when the socket errors before opening', async () => {
    const conn = await freshConnect('sess_1', {})
    const ws = MockWebSocket.instances[0]
    ws.emitError()
    await expect(conn.ready).resolves.toBe(false)
    conn.close()
  })

  it('ignores malformed frames without throwing', async () => {
    const tokens: string[] = []
    const conn = await freshConnect('sess_1', { onToken: (t) => tokens.push(t) })
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()
    await conn.ready
    ws.onmessage?.({ data: 'not-json' })
    ws.emitMessage({ type: 'unknown_type' })
    expect(tokens).toEqual([])
    conn.close()
  })

  it('skips reconnect during the failure cooldown', async () => {
    const first = await freshConnect('sess_1', {})
    MockWebSocket.instances[0].emitError()
    await first.ready
    first.close()

    const second = await freshConnect('sess_1', {})
    // No new socket was created while cooling down.
    expect(MockWebSocket.instances).toHaveLength(1)
    await expect(second.ready).resolves.toBe(false)
  })
})
