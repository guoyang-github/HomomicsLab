export type MessageType =
  | 'text'
  | 'todo_list'
  | 'hitl_request'
  | 'tool_call'
  | 'result_preview'
  | 'parameter_form'
  | 'file_reference'
  | 'plot'
  | 'error'
  | 'system'

import type { TaskNode, TaskProgress } from './tasks'

export interface TodoListContent {
  text: string
  tasks: TaskNode[]
  progress?: TaskProgress
}

export interface HITLContent {
  checkpoint: {
    id: string
    trigger_reason: string
    context_summary: string
    options: Array<{
      id: string
      label: string
      description?: string
    }>
    default_option?: {
      id: string
      label: string
    }
  }
  task_id: string
}

export interface PlotContent {
  image_base64: string
  plot_type: string
  title: string
  caption?: string
}

export interface ChatMessage {
  id: string
  type: MessageType
  content: string | Record<string, unknown>
  sender: 'user' | 'agent' | 'system'
  timestamp: string
  task_id?: string
  skill_id?: string
  related_files?: string[]
}
