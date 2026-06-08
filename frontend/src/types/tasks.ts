export type TaskStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'awaiting_human'
  | 'aborted'

export interface TaskNode {
  id: string
  name: string
  description: string
  phase: string
  status: TaskStatus
  dependencies: string[]
  agent_assignment?: string
  skills_required: string[]
  estimated_duration_minutes: number
  parameters: Record<string, unknown>
  result?: Record<string, unknown>
  error_message?: string
}

export interface TaskProgress {
  total: number
  pending: number
  running: number
  completed: number
  failed: number
  awaiting_human: number
  percent: number
}
