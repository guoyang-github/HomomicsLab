import { getRuntimeConfig } from '@/config'
import { useAuthStore } from '@/stores/authStore'

/**
 * Live chat turn streaming over the session WebSocket
 * (`/api/chat/ws/{session_id}`).
 *
 * The HTTP `/send` request still owns the authoritative result; this channel
 * only carries in-flight events while a turn runs:
 * - `{"type": "token", "token": "..."}` — streamed answer token
 * - `{"type": "token", "done": true}` — answer stream finished
 * - `{"type": "token", "reset": true}` — discard partial tokens (stream
 *    failed; the final answer arrives via the HTTP response)
 * - `{"type": "agent_event", "payload": {...}}` — progress events such as
 *   `{"type": "planning", "message": "..."}`
 *
 * Any connection failure degrades silently to the classic one-shot flow.
 */

export interface ChatStreamEvents {
  onToken?: (token: string) => void
  onDone?: () => void
  onReset?: () => void
  onAgentEvent?: (payload: Record<string, any>) => void
}

export interface ChatStreamConnection {
  /** Resolves true once the socket is open, false when unavailable. */
  ready: Promise<boolean>
  close: () => void
}

const READY_TIMEOUT_MS = 400
/** After a failed connect, skip reconnect attempts for this long so the
 *  degraded (non-streaming) path never pays the ready-timeout per message. */
const FAILURE_COOLDOWN_MS = 60_000

let lastFailureAt = 0

function getWsBase(): string {
  const { wsUrl, apiBaseUrl } = getRuntimeConfig()
  if (wsUrl) return wsUrl
  if (apiBaseUrl && apiBaseUrl !== '/api') {
    try {
      const url = new URL(apiBaseUrl)
      return `${url.protocol === 'https:' ? 'wss:' : 'ws:'}//${url.host}`
    } catch {
      // fall through to same-origin
    }
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}`
}

const noopConnection: ChatStreamConnection = {
  ready: Promise.resolve(false),
  close: () => {},
}

export function connectChatStream(
  sessionId: string,
  events: ChatStreamEvents
): ChatStreamConnection {
  if (Date.now() - lastFailureAt < FAILURE_COOLDOWN_MS) {
    return noopConnection
  }

  const params = new URLSearchParams()
  const token = useAuthStore.getState().token
  if (token) {
    params.set('token', token)
  }
  const query = params.toString()
  const url = `${getWsBase()}/api/chat/ws/${encodeURIComponent(sessionId)}${query ? `?${query}` : ''}`

  let socket: WebSocket | null = null
  try {
    socket = new WebSocket(url)
  } catch {
    lastFailureAt = Date.now()
    return noopConnection
  }

  let opened = false
  const ready = new Promise<boolean>((resolve) => {
    const timer = setTimeout(() => {
      if (!opened) {
        lastFailureAt = Date.now()
        resolve(false)
      }
    }, READY_TIMEOUT_MS)
    socket!.onopen = () => {
      opened = true
      clearTimeout(timer)
      resolve(true)
    }
    socket!.onerror = () => {
      if (!opened) {
        clearTimeout(timer)
        lastFailureAt = Date.now()
        resolve(false)
      }
    }
    socket!.onclose = () => {
      if (!opened) {
        clearTimeout(timer)
        lastFailureAt = Date.now()
        resolve(false)
      }
    }
  })

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data as string)
      if (data?.type === 'token') {
        if (data.reset) {
          events.onReset?.()
        }
        if (typeof data.token === 'string' && data.token) {
          events.onToken?.(data.token)
        }
        if (data.done) {
          events.onDone?.()
        }
      } else if (data?.type === 'agent_event') {
        events.onAgentEvent?.(
          typeof data.payload === 'object' && data.payload !== null ? data.payload : {}
        )
      }
    } catch {
      // Ignore malformed frames; the HTTP response remains authoritative.
    }
  }

  return {
    ready,
    close: () => {
      try {
        socket?.close()
      } catch {
        // already closed
      }
      socket = null
    },
  }
}
