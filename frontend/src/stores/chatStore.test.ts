import { describe, it, expect } from 'vitest'
import { useChatStore } from './chatStore'

describe('chatStore', () => {
  it('should add a message', () => {
    const store = useChatStore.getState()
    store.addMessage({
      id: '1',
      type: 'text',
      content: 'hello',
      sender: 'user',
      timestamp: new Date().toISOString(),
    })

    expect(useChatStore.getState().messages).toHaveLength(1)
    expect(useChatStore.getState().messages[0].content).toBe('hello')
  })

  it('should set typing state', () => {
    useChatStore.getState().setIsTyping(true)
    expect(useChatStore.getState().isTyping).toBe(true)
  })

  it('should create session scoped to current project', () => {
    useChatStore.getState().setProjectId('proj_1')
    const id = useChatStore.getState().createSession('My Session')
    const session = useChatStore.getState().sessions.find((s) => s.id === id)
    expect(session).toBeDefined()
    expect(session?.projectId).toBe('proj_1')
    expect(useChatStore.getState().currentProjectId).toBe('proj_1')
  })

  it('should create session with explicit project id', () => {
    const id = useChatStore.getState().createSession('Explicit', 'proj_2')
    const session = useChatStore.getState().sessions.find((s) => s.id === id)
    expect(session?.projectId).toBe('proj_2')
  })
})
