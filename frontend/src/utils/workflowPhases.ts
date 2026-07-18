import type { JobRuntime } from '@/stores/executionStore'
import type { WorkflowSkeleton, PhaseState } from '@/stores/executionStore'
import type { ChatMessage } from '@/types/chat'
import type { TaskNode } from '@/types/tasks'

/** A flow node synthesized from a domain pipeline skeleton phase. */
export type PhaseFlowTask = TaskNode & { fromPhase?: boolean }

/**
 * Convert a domain pipeline skeleton into flow tasks: one node per
 * non-skipped phase, chained serially in array order. Node status comes from
 * the live phase reports; phases without a report stay pending. Returns null
 * when there is no skeleton so callers fall back to the task-tree path.
 */
export function buildPhaseTasks(
  skeleton: WorkflowSkeleton | null | undefined,
  phaseStates: Record<string, PhaseState> | undefined
): PhaseFlowTask[] | null {
  if (!skeleton) return null
  const visible = skeleton.phases.filter((p) => !p.skipped)
  return visible.map((phase, index) => ({
    id: phase.phase_type,
    name: phase.name || phase.phase_type,
    description: '',
    phase: phase.phase_type,
    status: phaseStates?.[phase.phase_type]?.status ?? 'pending',
    dependencies: index === 0 ? [] : [visible[index - 1].phase_type],
    skills_required: [],
    estimated_duration_minutes: 0,
    parameters: {},
    fromPhase: true,
  }))
}

/**
 * Extract the domain hint carried by the latest todo_list / execution_plan
 * message. Backends may attach it to the plan/intent payload or to message
 * metadata (the sanctioned extension point). Returns null when no message
 * carries a domain.
 */
export function domainFromMessages(messages: ChatMessage[]): string | null {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const msg = messages[i]
    const type = typeof msg.type === 'string' ? msg.type.toLowerCase() : ''
    if (type !== 'todo_list' && type !== 'execution_plan') continue
    const content =
      typeof msg.content === 'object' && msg.content !== null
        ? (msg.content as Record<string, unknown>)
        : {}
    const plan = content.plan as Record<string, unknown> | undefined
    const intent = content.intent as Record<string, unknown> | undefined
    const candidates = [content.domain, plan?.domain, intent?.domain, msg.metadata?.domain]
    for (const candidate of candidates) {
      if (typeof candidate === 'string' && candidate) return candidate
    }
  }
  return null
}

export type WorkflowAvailability = 'domain' | 'legacy' | 'generic'

/**
 * Decide whether the workflow DAG view has meaningful data for the current
 * session:
 * - 'domain'  — a domain task (skeleton received or explicit domain hint);
 * - 'legacy'  — no domain signal but a task tree exists (fixed_pipeline /
 *               historical sessions keep the pre-skeleton rendering);
 * - 'generic' — positively generic (explicit `generic` hint, or nothing to
 *               show at all); workflow entries stay hidden.
 */
export function resolveWorkflowAvailability(options: {
  job: JobRuntime | null
  messages: ChatMessage[]
  hasTaskTree: boolean
}): WorkflowAvailability {
  const { job, messages, hasTaskTree } = options
  if (job?.workflowSkeleton) return 'domain'
  const domain = domainFromMessages(messages)
  if (domain) return domain === 'generic' ? 'generic' : 'domain'
  return hasTaskTree ? 'legacy' : 'generic'
}
