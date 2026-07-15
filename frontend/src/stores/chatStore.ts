import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { chatApi } from '@/services/api'
import type { ChatMessage } from '@/types/chat'
import { useTaskStore } from '@/stores/taskStore'
import { usePlanStore } from '@/stores/planStore'
import { useExecutionStore } from '@/stores/executionStore'
import { toastError } from '@/stores/toastStore'
import type { TaskProgress, TaskNode } from '@/types/tasks'
import type { PlanRequestContent } from '@/types/chat'

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
  selectSession: (id: string) => Promise<void>
  setProjectId: (id: string) => void
  setDraftInput: (value: string) => void
  clearMessages: () => void

  fetchSessions: (projectId?: string) => Promise<void>
  loadSessionMessages: (sessionId: string) => Promise<void>
  createSession: (name?: string, projectId?: string) => string
  renameSession: (id: string, name: string) => void
  deleteSession: (id: string) => void
  getCurrentSession: () => ChatSession | undefined
  sendMessage: (text: string) => Promise<void>
}

function _extractProgress(tasks: { status: string }[]): TaskProgress {
  const total = tasks.length
  const counts = {
    pending: 0,
    running: 0,
    completed: 0,
    failed: 0,
    awaiting_human: 0,
  }
  tasks.forEach((task) => {
    if (task.status in counts) {
      counts[task.status as keyof typeof counts]++
    }
  })
  return {
    total,
    ...counts,
    percent: total > 0 ? Math.round((counts.completed / total) * 100) : 0,
  }
}

function _extractTasksFromMessages(messages: ChatMessage[]): { tasks: TaskNode[]; status?: string } | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i]
    const type = typeof msg.type === 'string' ? msg.type.toLowerCase() : ''
    if (type !== 'todo_list' && type !== 'execution_plan') continue
    const content = typeof msg.content === 'object' && msg.content !== null ? (msg.content as Record<string, unknown>) : {}
    const rawTasks: unknown = Array.isArray(content.tasks)
      ? content.tasks
      : Array.isArray((content.plan as Record<string, unknown> | undefined)?.tasks)
      ? (content.plan as Record<string, unknown>).tasks
      : null
    const tasks = Array.isArray(rawTasks) ? rawTasks : null
    if (!tasks || tasks.length === 0) continue
    const topStatus = typeof content.status === 'string' ? content.status.toLowerCase() : undefined
    const normalized =
      topStatus === 'completed' || topStatus === 'failed'
        ? tasks.map((t: unknown) => ({ ...(t as TaskNode), status: topStatus }))
        : tasks
    return { tasks: normalized as TaskNode[], status: topStatus }
  }
  return null
}

function _syncExecutionStateFromMessages(messages: ChatMessage[]) {
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i]
    const type = typeof msg.type === 'string' ? msg.type.toLowerCase() : ''
    if (type !== 'todo_list') continue
    const content = typeof msg.content === 'object' && msg.content !== null ? (msg.content as Record<string, unknown>) : {}
    const status = typeof content.status === 'string' ? content.status.toLowerCase() : undefined
    if (status === 'completed' || status === 'failed') {
      useExecutionStore.getState().setStatus(status, status === 'completed' ? 100 : 0)
      return
    }
  }
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
      selectSession: async (id) => {
        set({ currentSessionId: id, messages: [] })
        usePlanStore.getState().discardDraft()
        useExecutionStore.getState().reset()
        useTaskStore.getState().setTaskTree([])
        useTaskStore.getState().setProgress({
          total: 0,
          pending: 0,
          running: 0,
          completed: 0,
          failed: 0,
          awaiting_human: 0,
          percent: 0,
        })
        await get().loadSessionMessages(id)
      },
      loadSessionMessages: async (sessionId) => {
        try {
          const response = await chatApi.getMessages(sessionId)
          const messages = response.data
          set({ messages })
          const extracted = _extractTasksFromMessages(messages)
          if (extracted && extracted.tasks.length > 0) {
            useTaskStore.getState().setTaskTree(extracted.tasks)
            useTaskStore.getState().setProgress(_extractProgress(extracted.tasks))
          }
          _syncExecutionStateFromMessages(messages)
        } catch (err) {
          // eslint-disable-next-line no-console
          console.error('Failed to load session messages', err)
        }
      },
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

      deleteSession: async (id) => {
        const previous = get().sessions
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
        })
        try {
          await chatApi.deleteSession(id)
          await get().fetchSessions(get().currentProjectId)
        } catch (err: any) {
          // If the backend does not know this session (e.g. it was only local),
          // keep it removed instead of restoring it.
          const status = err?.response?.status
          if (status !== 404) {
            // eslint-disable-next-line no-console
            console.error('Failed to delete session', err)
            set({ sessions: previous })
          }
        }
      },

      getCurrentSession: () => {
        const state = get()
        return state.sessions.find((s) => s.id === state.currentSessionId)
      },

      sendMessage: async (text: string) => {
        const trimmed = text.trim()
        if (!trimmed) return
        const state = get()
        let sessionId = state.currentSessionId
        if (!sessionId) {
          sessionId = get().createSession()
        }
        const currentSession = get().getCurrentSession()
        if (currentSession) {
          const isGenericName =
            currentSession.name === 'Default Session' || currentSession.name.startsWith('Session ')
          if (isGenericName) {
            get().renameSession(currentSession.id, trimmed.slice(0, 40))
          }
        }

        usePlanStore.getState().discardDraft()

        const userMessage: ChatMessage = {
          id: `msg_${Date.now()}`,
          type: 'text',
          content: trimmed,
          sender: 'user',
          timestamp: new Date().toISOString(),
        }
        get().addMessage(userMessage)
        get().setIsTyping(true)

        try {
          const response = await chatApi.sendMessage({
            project_id: state.currentProjectId,
            session_id: sessionId,
            message: trimmed,
          })

          const tasks = response.data.task_tree.tasks || []
          useTaskStore.getState().setTaskTree(tasks)
          useTaskStore.getState().setProgress(_extractProgress(tasks))

          if (response.data.status === 'awaiting_plan_approval' && response.data.plan) {
            const planContent: PlanRequestContent = {
              plan_id: response.data.plan_id || response.data.plan.plan_id,
              response_text: response.data.response,
              plan: response.data.plan,
            }
            usePlanStore.getState().loadPlan(planContent)
          } else {
            usePlanStore.getState().discardDraft()
          }

          get().setMessages(response.data.messages)

          if (response.data.job_id) {
            useExecutionStore.getState().startJob(response.data.job_id, sessionId)
            useTaskStore.getState().setTaskTree(tasks)
            useTaskStore.getState().setProgress(_extractProgress(tasks))
          }
        } catch (error: any) {
          const detail = error?.response?.data?.detail || error?.message
          const errorMessage: ChatMessage = {
            id: `msg_${Date.now()}_error`,
            type: 'error',
            content: detail || 'Send failed',
            sender: 'system',
            timestamp: new Date().toISOString(),
          }
          get().addMessage(errorMessage)
          toastError(detail || 'Send failed')
        } finally {
          get().setIsTyping(false)
        }
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
