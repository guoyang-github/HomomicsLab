export type MessageType =
  | 'text'
  | 'todo_list'
  | 'execution_plan'
  | 'hitl_request'
  | 'plan_request'
  | 'debate_request'
  | 'tool_call'
  | 'result_preview'
  | 'follow_up'
  | 'parameter_form'
  | 'file_reference'
  | 'plot'
  | 'plot_data'
  | 'artifact'
  | 'error'
  | 'system'

import type { TaskNode, TaskProgress } from './tasks'

export interface TodoListContent {
  text: string
  tasks: TaskNode[]
  progress?: TaskProgress
  job_id?: string
}

export interface PlanEstimates {
  total_estimated_cost_usd?: number
  total_estimated_duration_seconds?: number
}

export interface ExecutionPlanContent {
  plan_id: string
  response_text: string
  tasks: TaskNode[]
  progress?: TaskProgress
  estimates?: PlanEstimates
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
    metadata?: Record<string, unknown>
  }
  task_id: string
}

export interface PlanPhase {
  phase_type: string
  description?: string
  required?: boolean
  skill_id?: string
  readonly?: boolean
  parameters?: Record<string, unknown>
  parameter_recommendations?: Record<string, string>
  parameter_sources?: Record<string, string>
}

export interface PlanTransition {
  from: string
  to: string
  type: string
}

export interface PlanModification {
  phase_type: string
  action: 'update' | 'remove' | 'add' | 'update_dependency'
  parameter?: string
  old_value?: unknown
  new_value?: unknown
  after?: string
  before?: string
  description?: string
  required?: boolean
  skill_id?: string
  dependencies?: string[]
}

export interface FollowUpContent {
  suggestions: string[]
}

export interface PlanRequestContent {
  plan_id: string
  response_text: string
  plan: {
    plan_id: string
    status: string
    is_fallback: boolean
    intent_analysis_type: string
    phases: PlanPhase[]
    transitions?: PlanTransition[]
    gaps?: Array<Record<string, unknown>>
    suggestion_text?: string
    version: number
  }
}

export interface DebateOption {
  id: string
  label: string
  description?: string
  proposer?: string
  score?: number
}

export interface DebateRequestContent {
  debate_id: string
  topic: string
  options: DebateOption[]
  recommendation?: DebateOption
  round_summaries?: string[]
}

export interface PlotContent {
  image_base64: string
  plot_type: string
  title: string
  caption?: string
}

export interface PlotDataContent {
  plot_type: string
  title: string
  data: Record<string, unknown>
  caption?: string
}

export interface ChatMessageMetadata {
  /** Chain-of-thought / reasoning text rendered in a collapsible block. */
  reasoning?: string
  /** Alias some backends use instead of `reasoning`. */
  thinking?: string
  [key: string]: unknown
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
  metadata?: ChatMessageMetadata
}
