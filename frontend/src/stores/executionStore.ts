import { create } from 'zustand'

export interface LogEntry {
  id: string
  timestamp: string
  level: 'info' | 'stdout' | 'stderr' | 'error' | 'success' | 'warning' | 'tool' | 'artifact'
  message: string
  taskId?: string
}

interface ExecutionState {
  jobId: string | null
  jobSessionId: string | null
  isConnected: boolean
  logs: LogEntry[]
  status: 'idle' | 'running' | 'completed' | 'failed' | 'aborted'
  percent: number
  result: Record<string, any> | null

  setJobId: (id: string | null) => void
  setJobSessionId: (id: string | null) => void
  startJob: (jobId: string, sessionId: string) => void
  setConnected: (connected: boolean) => void
  setStatus: (status: ExecutionState['status'], percent?: number) => void
  addLog: (entry: Omit<LogEntry, 'id'>) => void
  clearLogs: () => void
  setResult: (result: Record<string, any> | null) => void
  reset: () => void
}

let logIdCounter = 0

export const useExecutionStore = create<ExecutionState>((set) => ({
  jobId: null,
  jobSessionId: null,
  isConnected: false,
  logs: [],
  status: 'idle',
  percent: 0,
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
      result: null,
    }),
  setConnected: (isConnected) => set({ isConnected }),
  setStatus: (status, percent) => set({ status, ...(percent !== undefined && { percent }) }),
  addLog: (entry) =>
    set((state) => ({
      logs: [
        ...state.logs,
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
      result: null,
    }),
}))
