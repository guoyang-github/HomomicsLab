import { useState } from 'react'
import { useChatStore } from '@/stores/chatStore'
import { useTaskStore } from '@/stores/taskStore'
import { chatApi } from '@/services/api'
import type { ChatMessage } from '@/types/chat'
import type { TaskProgress } from '@/types/tasks'

export function ChatInput() {
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const { addMessage, currentSessionId, currentProjectId, setIsTyping } = useChatStore()
  const { setTaskTree, setProgress } = useTaskStore()

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const userMessage: ChatMessage = {
      id: `msg_${Date.now()}`,
      type: 'text',
      content: input,
      sender: 'user',
      timestamp: new Date().toISOString(),
    }
    addMessage(userMessage)
    setInput('')
    setIsLoading(true)
    setIsTyping(true)

    try {
      const response = await chatApi.sendMessage({
        project_id: currentProjectId,
        session_id: currentSessionId,
        message: input,
      })

      // Update task store with the task tree from response
      const tasks = response.data.task_tree.tasks
      setTaskTree(tasks)
      const lastMsg = response.data.messages[response.data.messages.length - 1]
      if (lastMsg?.content && typeof lastMsg.content === 'object' && lastMsg.content !== null && 'progress' in lastMsg.content) {
        const content = lastMsg.content as unknown as { progress?: TaskProgress }
        if (content.progress) {
          setProgress(content.progress)
        }
      }

      const agentMessage: ChatMessage = {
        id: `msg_${Date.now()}_agent`,
        type: 'todo_list',
        content: {
          text: response.data.response,
          tasks: tasks,
        },
        sender: 'agent',
        timestamp: new Date().toISOString(),
      }
      addMessage(agentMessage)
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: `msg_${Date.now()}_error`,
        type: 'error',
        content: 'Failed to send message. Please try again.',
        sender: 'system',
        timestamp: new Date().toISOString(),
      }
      addMessage(errorMessage)
    } finally {
      setIsLoading(false)
      setIsTyping(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="border-t border-slate-200 p-4 bg-white">
      <div className="flex gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="描述您的分析需求..."
          rows={2}
          className="flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
        />
        <button
          onClick={handleSend}
          disabled={isLoading || !input.trim()}
          className="rounded-lg bg-primary px-4 py-2 text-white text-sm font-medium disabled:opacity-50 hover:bg-blue-700"
        >
          {isLoading ? '发送中...' : '发送'}
        </button>
      </div>
    </div>
  )
}
