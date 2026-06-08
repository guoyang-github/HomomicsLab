export type MessageType =
  | 'text'
  | 'todo_list'
  | 'hitl_request'
  | 'tool_call'
  | 'result_preview'
  | 'parameter_form'
  | 'file_reference'
  | 'error'
  | 'system'

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
