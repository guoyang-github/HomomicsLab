import { create } from 'zustand'

export interface LogEntry {
  id: string
  timestamp: string
  level: 'info' | 'stdout' | 'stderr' | 'error' | 'success'
  message: string
  taskId?: string
}

interface ExecutionState {
  jobId: string | null
  isConnected: boolean
  logs: LogEntry[]
  status: 'idle' | 'running' | 'completed' | 'failed' | 'aborted'
  percent: number

  setJobId: (id: string | null) => void
  setConnected: (connected: boolean) => void
  setStatus: (status: ExecutionState['status'], percent?: number) => void
  addLog: (entry: Omit<LogEntry, 'id'>) => void
  clearLogs: () => void
  reset: () => void
}

let logIdCounter = 0

export const useExecutionStore = create<ExecutionState>((set) => ({
  jobId: null,
  isConnected: false,
  logs: [],
  status: 'idle',
  percent: 0,

  setJobId: (jobId) => set({ jobId }),
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
  reset: () => set({ jobId: null, isConnected: false, logs: [], status: 'idle', percent: 0 }),
}))
