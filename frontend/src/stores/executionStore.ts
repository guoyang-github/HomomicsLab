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

export type ExecutionStatus = 'idle' | 'running' | 'completed' | 'failed' | 'aborted'

/** One phase of a domain pipeline skeleton, after preflight pruning. */
export interface WorkflowSkeletonPhase {
  phase_type: string
  name: string
  skipped: boolean
}

/** Domain pipeline skeleton announced by the backend when execution starts.
 * Only domain tasks (domain != generic) receive one; it drives the workflow
 * DAG view instead of the task tree. */
export interface WorkflowSkeleton {
  domain: string
  phases: WorkflowSkeletonPhase[]
}

export type PhaseStatus = 'pending' | 'running' | 'completed' | 'failed'

/** Live execution state of one skeleton phase, reported via phase events. */
export interface PhaseState {
  status: PhaseStatus
  params?: Record<string, unknown>
  updatedAt: number
}

/** Runtime state of a single execution job. Jobs are keyed by id and survive
 * session switches, so switching away and back restores the live view. */
export interface JobRuntime {
  /** Session this job was started from. */
  sessionId: string
  isConnected: boolean
  logs: LogEntry[]
  status: ExecutionStatus
  percent: number
  currentPhase: string | null
  result: Record<string, any> | null
  /** Domain pipeline skeleton; null for generic tasks and legacy sessions. */
  workflowSkeleton: WorkflowSkeleton | null
  /** Per-phase execution state keyed by phase_type. */
  phaseStates: Record<string, PhaseState>
  /** Last mutation time in ms; drives terminal-job eviction. */
  updatedAt: number
}

export interface ExecutionState {
  /** Per-job runtime state, keyed by job id. */
  jobs: Record<string, JobRuntime>
  /** The job currently displayed for each session (session id → job id). */
  activeJobIdBySession: Record<string, string>

  startJob: (jobId: string, sessionId: string) => void
  restoreJob: (
    jobId: string,
    sessionId: string,
    logs?: LogEntry[],
    status?: ExecutionStatus,
    percent?: number,
    currentPhase?: string | null
  ) => void
  setConnected: (jobId: string, connected: boolean) => void
  setStatus: (jobId: string, status: ExecutionStatus, percent?: number, currentPhase?: string | null) => void
  setCurrentPhase: (jobId: string, phase: string | null) => void
  /** Store the domain pipeline skeleton announced at execution start. */
  setWorkflowSkeleton: (jobId: string, skeleton: WorkflowSkeleton) => void
  /**
   * Record a phase progress report. Raw backend statuses are accepted and
   * normalized: start→running, done→completed, failed→failed. Unknown values
   * are ignored.
   */
  setPhaseState: (jobId: string, phaseType: string, status: string, params?: Record<string, unknown>) => void
  addLog: (jobId: string, entry: Omit<LogEntry, 'id'>) => void
  clearLogs: (jobId: string) => void
  setResult: (jobId: string, result: Record<string, any> | null) => void
  /** Point a session at a job (or clear the pointer with null). */
  setActiveJob: (sessionId: string, jobId: string | null) => void
  /** Clear the session's active pointer without touching job runtime data. */
  deactivate: (sessionId: string) => void
  /** Drop a job's runtime data and any session pointers referencing it. */
  removeJob: (jobId: string) => void
  /** Full wipe (test teardown). Normal session flows use deactivate/removeJob. */
  reset: () => void
}

let logIdCounter = 0

/** Hard cap on retained execution logs per job; the oldest entries are dropped first. */
export const MAX_LOG_ENTRIES = 2000
/**
 * Truncation trigger: only slice once the buffer exceeds this threshold and
 * cut back to MAX_LOG_ENTRIES, so appends stay amortized O(1) instead of
 * copying the whole array on every log line.
 */
const LOG_TRUNCATE_THRESHOLD = MAX_LOG_ENTRIES + 200

/**
 * Soft cap on retained terminal (completed/failed/aborted) jobs. Once exceeded,
 * the oldest terminal jobs are evicted; jobs still referenced by a session's
 * active pointer are never evicted (the cap may stay exceeded in that case).
 */
export const MAX_TERMINAL_JOBS = 20

const TERMINAL_STATUSES: ReadonlySet<ExecutionStatus> = new Set(['completed', 'failed', 'aborted'])

function createJobRuntime(sessionId: string): JobRuntime {
  return {
    sessionId,
    isConnected: false,
    logs: [],
    status: 'running',
    percent: 0,
    currentPhase: null,
    result: null,
    workflowSkeleton: null,
    phaseStates: {},
    updatedAt: Date.now(),
  }
}

/** Normalize a raw phase-event status to the canonical PhaseStatus, or null
 * when the value is not recognized. */
function normalizePhaseStatus(raw: string): PhaseStatus | null {
  switch (raw) {
    case 'start':
    case 'running':
      return 'running'
    case 'done':
    case 'completed':
      return 'completed'
    case 'failed':
      return 'failed'
    case 'pending':
      return 'pending'
    default:
      return null
  }
}

function evictTerminalJobs(
  jobs: Record<string, JobRuntime>,
  activeJobIdBySession: Record<string, string>
): Record<string, JobRuntime> {
  const terminalIds = Object.keys(jobs).filter((id) => TERMINAL_STATUSES.has(jobs[id].status))
  if (terminalIds.length <= MAX_TERMINAL_JOBS) return jobs
  const referenced = new Set(Object.values(activeJobIdBySession))
  const sorted = terminalIds.sort((a, b) => jobs[a].updatedAt - jobs[b].updatedAt)
  const next = { ...jobs }
  let remaining = terminalIds.length
  for (const id of sorted) {
    if (remaining <= MAX_TERMINAL_JOBS) break
    if (referenced.has(id)) continue
    delete next[id]
    remaining -= 1
  }
  return next
}

/** Resolve the job id currently displayed for a session. */
export function selectActiveJobId(
  state: Pick<ExecutionState, 'activeJobIdBySession'>,
  sessionId: string | null | undefined
): string | null {
  if (!sessionId) return null
  return state.activeJobIdBySession[sessionId] ?? null
}

/** Resolve the full runtime of the job currently displayed for a session. */
export function selectActiveJob(
  state: Pick<ExecutionState, 'jobs' | 'activeJobIdBySession'>,
  sessionId: string | null | undefined
): JobRuntime | null {
  const jobId = selectActiveJobId(state, sessionId)
  return jobId ? state.jobs[jobId] ?? null : null
}

export const useExecutionStore = create<ExecutionState>((set) => ({
  jobs: {},
  activeJobIdBySession: {},

  startJob: (jobId, sessionId) =>
    set((state) => ({
      jobs: { ...state.jobs, [jobId]: createJobRuntime(sessionId) },
      activeJobIdBySession: { ...state.activeJobIdBySession, [sessionId]: jobId },
    })),
  restoreJob: (jobId, sessionId, logs, status, percent, currentPhase) =>
    set((state) => {
      const existing = state.jobs[jobId]
      const nextStatus = status || existing?.status || 'running'
      const next: JobRuntime = {
        sessionId,
        isConnected: existing?.isConnected ?? false,
        // Keep the richer in-memory log buffer when one exists; trace-rebuilt
        // logs only seed jobs we hold no local data for.
        logs: existing && existing.logs.length > 0 ? existing.logs : logs || [],
        status: nextStatus,
        percent: percent ?? existing?.percent ?? 0,
        currentPhase: currentPhase !== undefined ? currentPhase : existing?.currentPhase ?? null,
        result: existing?.result ?? null,
        workflowSkeleton: existing?.workflowSkeleton ?? null,
        phaseStates: existing?.phaseStates ?? {},
        updatedAt: Date.now(),
      }
      const activeJobIdBySession = { ...state.activeJobIdBySession, [sessionId]: jobId }
      const jobs = { ...state.jobs, [jobId]: next }
      return {
        jobs: TERMINAL_STATUSES.has(nextStatus) ? evictTerminalJobs(jobs, activeJobIdBySession) : jobs,
        activeJobIdBySession,
      }
    }),
  setConnected: (jobId, isConnected) =>
    set((state) => {
      const job = state.jobs[jobId]
      if (!job) return state
      return { jobs: { ...state.jobs, [jobId]: { ...job, isConnected, updatedAt: Date.now() } } }
    }),
  setStatus: (jobId, status, percent, currentPhase) =>
    set((state) => {
      const job = state.jobs[jobId]
      if (!job) return state
      const jobs = {
        ...state.jobs,
        [jobId]: {
          ...job,
          status,
          ...(percent !== undefined && { percent }),
          ...(currentPhase !== undefined && { currentPhase }),
          updatedAt: Date.now(),
        },
      }
      return { jobs: TERMINAL_STATUSES.has(status) ? evictTerminalJobs(jobs, state.activeJobIdBySession) : jobs }
    }),
  setCurrentPhase: (jobId, currentPhase) =>
    set((state) => {
      const job = state.jobs[jobId]
      if (!job) return state
      return { jobs: { ...state.jobs, [jobId]: { ...job, currentPhase, updatedAt: Date.now() } } }
    }),
  setWorkflowSkeleton: (jobId, skeleton) =>
    set((state) => {
      const job = state.jobs[jobId]
      if (!job) return state
      return { jobs: { ...state.jobs, [jobId]: { ...job, workflowSkeleton: skeleton, updatedAt: Date.now() } } }
    }),
  setPhaseState: (jobId, phaseType, status, params) =>
    set((state) => {
      const job = state.jobs[jobId]
      if (!job) return state
      const normalized = normalizePhaseStatus(status)
      if (!normalized) return state
      const existing = job.phaseStates[phaseType]
      const phaseStates = {
        ...job.phaseStates,
        [phaseType]: {
          status: normalized,
          params: params ?? existing?.params,
          updatedAt: Date.now(),
        },
      }
      return { jobs: { ...state.jobs, [jobId]: { ...job, phaseStates, updatedAt: Date.now() } } }
    }),
  addLog: (jobId, entry) =>
    set((state) => {
      const job = state.jobs[jobId]
      if (!job) return state
      const logs = [
        ...(job.logs.length >= LOG_TRUNCATE_THRESHOLD
          ? job.logs.slice(job.logs.length - MAX_LOG_ENTRIES)
          : job.logs),
        {
          ...entry,
          id: `log_${Date.now()}_${++logIdCounter}`,
        },
      ]
      return { jobs: { ...state.jobs, [jobId]: { ...job, logs, updatedAt: Date.now() } } }
    }),
  clearLogs: (jobId) =>
    set((state) => {
      const job = state.jobs[jobId]
      if (!job) return state
      return { jobs: { ...state.jobs, [jobId]: { ...job, logs: [], updatedAt: Date.now() } } }
    }),
  setResult: (jobId, result) =>
    set((state) => {
      const job = state.jobs[jobId]
      if (!job) return state
      return { jobs: { ...state.jobs, [jobId]: { ...job, result, updatedAt: Date.now() } } }
    }),
  setActiveJob: (sessionId, jobId) =>
    set((state) => {
      const activeJobIdBySession = { ...state.activeJobIdBySession }
      if (jobId === null) {
        delete activeJobIdBySession[sessionId]
      } else {
        activeJobIdBySession[sessionId] = jobId
      }
      return { activeJobIdBySession }
    }),
  deactivate: (sessionId) =>
    set((state) => {
      if (!(sessionId in state.activeJobIdBySession)) return state
      const activeJobIdBySession = { ...state.activeJobIdBySession }
      delete activeJobIdBySession[sessionId]
      return { activeJobIdBySession }
    }),
  removeJob: (jobId) =>
    set((state) => {
      if (!state.jobs[jobId]) return state
      const jobs = { ...state.jobs }
      delete jobs[jobId]
      const activeJobIdBySession = { ...state.activeJobIdBySession }
      for (const [sid, jid] of Object.entries(activeJobIdBySession)) {
        if (jid === jobId) delete activeJobIdBySession[sid]
      }
      return { jobs, activeJobIdBySession }
    }),
  reset: () => set({ jobs: {}, activeJobIdBySession: {} }),
}))
