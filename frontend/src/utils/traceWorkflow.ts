import type { WorkflowSkeleton } from '@/stores/executionStore'

/** One phase progress marker recovered from a mirrored trace node. Statuses
 * are the raw backend values (start/done/failed); normalization happens in
 * the execution store. */
export interface TracePhaseEvent {
  phase: string
  status: string
  params?: Record<string, unknown>
}

export interface TraceWorkflowRestore {
  skeleton: WorkflowSkeleton | null
  phaseEvents: TracePhaseEvent[]
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

/**
 * Extract the domain workflow skeleton and phase progress markers mirrored
 * into the execution trace by the backend
 * (``orchestrator_executors._trace_workflow_event``):
 *
 * - ``node_type == "plan"``  + ``metadata.event == "workflow_skeleton"``
 *   carries ``metadata.domain`` and ``metadata.phases`` (phase_type/name/
 *   skipped per entry).
 * - ``node_type == "phase"`` + ``metadata.event == "phase"``
 *   carries ``metadata.phase`` / ``metadata.status`` / ``metadata.params``.
 *
 * Other plan/phase trace nodes — the trace root (empty metadata), per-task
 * markers (``metadata: {phase, task_id}``) and open-agent steps (no
 * metadata) — carry no ``metadata.event`` and are ignored. Fault-tolerant by
 * design: malformed entries are dropped silently, mirroring the live-SSE
 * handler in ``useExecutionSSE``.
 */
export function extractWorkflowFromTrace(nodes: unknown): TraceWorkflowRestore {
  const result: TraceWorkflowRestore = { skeleton: null, phaseEvents: [] }
  if (!Array.isArray(nodes)) return result

  for (const raw of nodes) {
    const node = asRecord(raw)
    if (!node) continue
    const metadata = asRecord(node.metadata)
    if (!metadata) continue

    if (node.node_type === 'plan' && metadata.event === 'workflow_skeleton') {
      const domain = typeof metadata.domain === 'string' ? metadata.domain : ''
      const rawPhases = Array.isArray(metadata.phases) ? metadata.phases : []
      const phases = rawPhases
        .map((p) => asRecord(p))
        .filter((p): p is Record<string, unknown> => p !== null)
        .filter((p) => typeof p.phase_type === 'string' && p.phase_type)
        .map((p) => ({
          phase_type: p.phase_type as string,
          name: typeof p.name === 'string' && p.name ? p.name : (p.phase_type as string),
          skipped: p.skipped === true,
        }))
      // Last one wins when a trace holds more than one skeleton mirror.
      if (domain && phases.length > 0) {
        result.skeleton = { domain, phases }
      }
    } else if (node.node_type === 'phase' && metadata.event === 'phase') {
      if (typeof metadata.phase !== 'string' || !metadata.phase) continue
      if (typeof metadata.status !== 'string' || !metadata.status) continue
      result.phaseEvents.push({
        phase: metadata.phase,
        status: metadata.status,
        params: asRecord(metadata.params) ?? undefined,
      })
    }
  }
  return result
}
