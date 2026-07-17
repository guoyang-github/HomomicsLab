import { useChatStore } from '@/stores/chatStore'
import { useExecutionStore, selectActiveJobId } from '@/stores/executionStore'
import type { JobRuntime } from '@/stores/executionStore'

/**
 * The execution job currently attached to the active chat session.
 * Each session keeps its own active-job pointer, so this automatically
 * follows session switches without losing other sessions' job data.
 */
export function useActiveExecutionJob(): { jobId: string | null; job: JobRuntime | null } {
  const currentSessionId = useChatStore((state) => state.currentSessionId)
  const jobId = useExecutionStore((state) => selectActiveJobId(state, currentSessionId))
  const job = useExecutionStore((state) => (jobId ? state.jobs[jobId] ?? null : null))
  return { jobId, job }
}
