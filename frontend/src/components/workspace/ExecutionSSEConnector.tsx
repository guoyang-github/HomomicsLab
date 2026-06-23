import { useExecutionStore } from '@/stores/executionStore'
import { useExecutionSSE } from '@/hooks/useExecutionSSE'

export function ExecutionSSEConnector() {
  const jobId = useExecutionStore((state) => state.jobId)
  useExecutionSSE(jobId)
  return null
}
