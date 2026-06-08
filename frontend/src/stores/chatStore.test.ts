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
})
