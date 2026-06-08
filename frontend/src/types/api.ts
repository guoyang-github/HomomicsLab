import type { ChatMessage } from './chat'
import type { TaskNode } from './tasks'

export interface Project {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
}

export interface SendMessageRequest {
  project_id: string
  session_id: string
  message: string
}

export interface SendMessageResponse {
  response: string
  task_tree: { tasks: TaskNode[] }
  messages: ChatMessage[]
}

export interface FileUploadResponse {
  filename: string
  path: string
  size: number
}
