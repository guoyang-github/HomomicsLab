import { create } from 'zustand'

export interface LogEntry {
  id: string
  timestamp: string
  level: 'info' | 'stdout' | 'stderr' | 'error' | 'success' | 'warning' | 'tool' | 'artifact'
  message: string
  taskId?: string
  /** Set when the event comes from a sub-executor, e.g. "subagent:<skill_id>". */
  actor?: string
  /** Parent job/task id of the sub-executor that produced the event. */
  parentId?: string
  /** Terminal marker for the sub-executor group this entry belongs to. */
  subStatus?: 'completed' | 'failed'
}

export interface ExecutionState {
  jobId: string | null
  jobSessionId: string | null
  isConnected: boolean
  logs: LogEntry[]
  status: 'idle' | 'running' | 'completed' | 'failed' | 'aborted'
  percent: number
  currentPhase: string | null
  result: Record<string, any> | null

  setJobId: (id: string | null) => void
  setJobSessionId: (id: string | null) => void
  startJob: (jobId: string, sessionId: string) => void
  restoreJob: (jobId: string, sessionId: string, logs?: LogEntry[], status?: ExecutionState['status'], percent?: number, currentPhase?: string | null) => void
  setConnected: (connected: boolean) => void
  setStatus: (status: ExecutionState['status'], percent?: number, currentPhase?: string | null) => void
  setCurrentPhase: (phase: string | null) => void
  addLog: (entry: Omit<LogEntry, 'id'>) => void
  clearLogs: () => void
  setResult: (result: Record<string, any> | null) => void
  reset: () => void
}

let logIdCounter = 0

/** Hard cap on retained execution logs; the oldest entries are dropped first. */
export const MAX_LOG_ENTRIES = 2000
/**
 * Truncation trigger: only slice once the buffer exceeds this threshold and
 * cut back to MAX_LOG_ENTRIES, so appends stay amortized O(1) instead of
 * copying the whole array on every log line.
 */
const LOG_TRUNCATE_THRESHOLD = MAX_LOG_ENTRIES + 200

export const useExecutionStore = create<ExecutionState>((set) => ({
  jobId: null,
  jobSessionId: null,
  isConnected: false,
  logs: [],
  status: 'idle',
  percent: 0,
  currentPhase: null,
  result: null,

  setJobId: (jobId) => set({ jobId }),
  setJobSessionId: (jobSessionId) => set({ jobSessionId }),
  startJob: (jobId, jobSessionId) =>
    set({
      jobId,
      jobSessionId,
      isConnected: false,
      logs: [],
      status: 'running',
      percent: 0,
      currentPhase: null,
      result: null,
    }),
  restoreJob: (jobId, jobSessionId, logs, status, percent, currentPhase) =>
    set({
      jobId,
      jobSessionId,
      isConnected: false,
      logs: logs || [],
      status: status || 'running',
      percent: percent ?? 0,
      currentPhase: currentPhase ?? null,
      result: null,
    }),
  setConnected: (isConnected) => set({ isConnected }),
  setStatus: (status, percent, currentPhase) =>
    set({
      status,
      ...(percent !== undefined && { percent }),
      ...(currentPhase !== undefined && { currentPhase }),
    }),
  setCurrentPhase: (currentPhase) => set({ currentPhase }),
  addLog: (entry) =>
    set((state) => ({
      logs: [
        ...(state.logs.length >= LOG_TRUNCATE_THRESHOLD
          ? state.logs.slice(state.logs.length - MAX_LOG_ENTRIES)
          : state.logs),
        {
          ...entry,
          id: `log_${Date.now()}_${++logIdCounter}`,
        },
      ],
    })),
  clearLogs: () => set({ logs: [] }),
  setResult: (result) => set({ result }),
  reset: () =>
    set({
      jobId: null,
      jobSessionId: null,
      isConnected: false,
      logs: [],
      status: 'idle',
      percent: 0,
      currentPhase: null,
      result: null,
    }),
}))
