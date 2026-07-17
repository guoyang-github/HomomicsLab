import { useActiveExecutionJob } from '@/hooks/useActiveExecutionJob'
import { useExecutionSSE } from '@/hooks/useExecutionSSE'

export function ExecutionSSEConnector() {
  const { jobId } = useActiveExecutionJob()
  useExecutionSSE(jobId)
  return null
}
