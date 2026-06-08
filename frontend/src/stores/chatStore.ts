import { create } from 'zustand'
import type { ChatMessage } from '@/types/chat'

interface ChatState {
  messages: ChatMessage[]
  isTyping: boolean
  currentSessionId: string
  currentProjectId: string

  addMessage: (message: ChatMessage) => void
  setMessages: (messages: ChatMessage[]) => void
  setIsTyping: (typing: boolean) => void
  setSessionId: (id: string) => void
  setProjectId: (id: string) => void
  clearMessages: () => void
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isTyping: false,
  currentSessionId: `sess_${Date.now()}`,
  currentProjectId: 'default',

  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),

  setMessages: (messages) => set({ messages }),
  setIsTyping: (isTyping) => set({ isTyping }),
  setSessionId: (currentSessionId) => set({ currentSessionId }),
  setProjectId: (currentProjectId) => set({ currentProjectId }),
  clearMessages: () => set({ messages: [] }),
}))
