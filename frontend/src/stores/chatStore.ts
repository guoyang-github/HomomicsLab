import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { chatApi } from '@/services/api'
import type { ChatMessage } from '@/types/chat'

export interface ChatSession {
  id: string
  name: string
  projectId: string
  createdAt: string
  updatedAt: string
}

interface ChatState {
  sessions: ChatSession[]
  messages: ChatMessage[]
  isTyping: boolean
  currentSessionId: string
  currentProjectId: string
  draftInput: string
  sessionsLoading: boolean

  addMessage: (message: ChatMessage) => void
  setMessages: (messages: ChatMessage[]) => void
  setIsTyping: (typing: boolean) => void
  setSessionId: (id: string) => void
  setProjectId: (id: string) => void
  setDraftInput: (value: string) => void
  clearMessages: () => void

  fetchSessions: (projectId?: string) => Promise<void>
  createSession: (name?: string, projectId?: string) => string
  renameSession: (id: string, name: string) => void
  deleteSession: (id: string) => void
  getCurrentSession: () => ChatSession | undefined
}

function normalizeSession(raw: Record<string, unknown>): ChatSession {
  const updatedAt = typeof raw.updated_at === 'string' ? raw.updated_at : new Date().toISOString()
  return {
    id: String(raw.id),
    name: typeof raw.name === 'string' ? raw.name : 'New Session',
    projectId: typeof raw.project_id === 'string' ? raw.project_id : 'default',
    createdAt: typeof raw.created_at === 'string' ? raw.created_at : updatedAt,
    updatedAt,
  }
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      sessions: [],
      messages: [],
      isTyping: false,
      currentSessionId: '',
      currentProjectId: 'default',
      draftInput: '',
      sessionsLoading: false,

      addMessage: (message) =>
        set((state) => {
          const newMessages = [...state.messages, message]
          const sessionIndex = state.sessions.findIndex((s) => s.id === state.currentSessionId)
          const newSessions = [...state.sessions]
          if (sessionIndex >= 0) {
            newSessions[sessionIndex] = {
              ...newSessions[sessionIndex],
              updatedAt: new Date().toISOString(),
            }
          }
          return { messages: newMessages, sessions: newSessions }
        }),

      setMessages: (messages) => set({ messages }),
      setIsTyping: (isTyping) => set({ isTyping }),
      setSessionId: (currentSessionId) => set({ currentSessionId }),
      setProjectId: (currentProjectId) => set({ currentProjectId }),
      setDraftInput: (draftInput) => set({ draftInput }),
      clearMessages: () => set({ messages: [] }),

      fetchSessions: async (projectId) => {
        set({ sessionsLoading: true })
        try {
          const response = await chatApi.listSessions(projectId)
          const sessions = (response.data as unknown as Record<string, unknown>[]).map(normalizeSession)
          set((state) => {
            const next: Partial<ChatState> = { sessions, sessionsLoading: false }
            const stillExists = sessions.some((s) => s.id === state.currentSessionId)
            if (!stillExists && sessions.length > 0) {
              next.currentSessionId = sessions[0].id
              next.currentProjectId = sessions[0].projectId
              next.messages = []
            }
            return next
          })
        } catch (err) {
          set({ sessionsLoading: false })
          // eslint-disable-next-line no-console
          console.error('Failed to load sessions', err)
        }
      },

      createSession: (name?: string, projectId?: string) => {
        const id = `sess_${Date.now()}`
        const resolvedProjectId = projectId || get().currentProjectId || 'default'
        const newSession: ChatSession = {
          id,
          name: name || `Session ${new Date().toLocaleString()}`,
          projectId: resolvedProjectId,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        }
        set((state) => ({
          sessions: [newSession, ...state.sessions],
          currentSessionId: id,
          currentProjectId: resolvedProjectId,
          messages: [],
        }))
        return id
      },

      renameSession: (id, name) =>
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === id ? { ...s, name, updatedAt: new Date().toISOString() } : s
          ),
        })),

      deleteSession: (id) =>
        set((state) => {
          const remaining = state.sessions.filter((s) => s.id !== id)
          if (state.currentSessionId === id && remaining.length > 0) {
            return {
              sessions: remaining,
              currentSessionId: remaining[0].id,
              currentProjectId: remaining[0].projectId,
              messages: [],
            }
          }
          return { sessions: remaining }
        }),

      getCurrentSession: () => {
        const state = get()
        return state.sessions.find((s) => s.id === state.currentSessionId)
      },
    }),
    {
      name: 'homomics-chat',
      partialize: (state) => ({
        sessions: state.sessions,
        currentSessionId: state.currentSessionId,
        currentProjectId: state.currentProjectId,
      }),
    }
  )
)
