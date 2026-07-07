import { useEffect, useRef, useState, useCallback } from 'react'

import { useAuthStore } from '@/stores/authStore'
import { getRuntimeConfig } from '@/config'

export interface PresenceUser {
  user_id: string
  cursor_x?: number | null
  cursor_y?: number | null
  editing?: boolean
  color?: string | null
}

interface PresenceMessage {
  type: 'user_joined' | 'user_left' | 'presence'
  user?: PresenceUser
  user_id?: string
}

const USER_COLORS = ['#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899']

function getWsBaseFromApiBase(apiBaseUrl: string): string {
  if (!apiBaseUrl || apiBaseUrl === '/api') {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}`
  }
  try {
    const url = new URL(apiBaseUrl)
    const wsProtocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${wsProtocol}//${url.host}`
  } catch {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}`
  }
}

function pickColor(userId: string): string {
  let hash = 0
  for (let i = 0; i < userId.length; i++) {
    hash = userId.charCodeAt(i) + ((hash << 5) - hash)
  }
  return USER_COLORS[Math.abs(hash) % USER_COLORS.length]
}

export function usePresence(projectId: string | null, userId: string) {
  const socketRef = useRef<WebSocket | null>(null)
  const [users, setUsers] = useState<PresenceUser[]>([])
  const [isConnected, setIsConnected] = useState(false)

  const sendCursor = useCallback((x: number, y: number) => {
    const socket = socketRef.current
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'cursor', cursor_x: x, cursor_y: y }))
    }
  }, [])

  const sendEditing = useCallback((editing: boolean) => {
    const socket = socketRef.current
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'editing', editing }))
    }
  }, [])

  useEffect(() => {
    if (!projectId) {
      return
    }

    const token = useAuthStore.getState().token
    const params = new URLSearchParams({ user_id: userId })
    if (token) {
      params.set('token', token)
    }
    const wsBase = getRuntimeConfig().wsUrl || getWsBaseFromApiBase(getRuntimeConfig().apiBaseUrl)
    const wsUrl = `${wsBase}/collab/${projectId}/ws?${params.toString()}`
    const socket = new WebSocket(wsUrl)
    socketRef.current = socket

    socket.onopen = () => {
      setIsConnected(true)
      socket.send(JSON.stringify({ type: 'identify', color: pickColor(userId) }))
    }

    socket.onclose = () => {
      setIsConnected(false)
      setUsers([])
    }

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as PresenceMessage
        if (data.type === 'user_joined' && data.user) {
          setUsers((prev) => {
            const filtered = prev.filter((u) => u.user_id !== data.user!.user_id)
            return [...filtered, data.user!]
          })
        } else if (data.type === 'user_left' && data.user_id) {
          setUsers((prev) => prev.filter((u) => u.user_id !== data.user_id))
        } else if (data.type === 'presence' && data.user) {
          setUsers((prev) => {
            const filtered = prev.filter((u) => u.user_id !== data.user!.user_id)
            return [...filtered, data.user!]
          })
        }
      } catch {
        // Ignore malformed messages.
      }
    }

    return () => {
      socket.close()
      socketRef.current = null
    }
  }, [projectId, userId])

  return { users, isConnected, sendCursor, sendEditing }
}
