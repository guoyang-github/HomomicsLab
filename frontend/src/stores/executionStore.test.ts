import { describe, it, expect, beforeEach } from 'vitest'
import {
  useExecutionStore,
  selectActiveJob,
  selectActiveJobId,
  MAX_LOG_ENTRIES,
  MAX_TERMINAL_JOBS,
} from './executionStore'
import type { JobRuntime } from './executionStore'

function makeLog(message: string) {
  return { timestamp: new Date().toISOString(), level: 'info' as const, message }
}

function terminalJob(updatedAt: number): JobRuntime {
  return {
    sessionId: 'sess_x',
    isConnected: false,
    logs: [],
    status: 'completed',
    percent: 100,
    currentPhase: null,
    result: null,
    updatedAt,
  }
}

function seedTerminalJobs(count: number) {
  const jobs: Record<string, JobRuntime> = {}
  for (let i = 0; i < count; i += 1) {
    jobs[`job_${i}`] = terminalJob(1000 + i)
  }
  useExecutionStore.setState({ jobs, activeJobIdBySession: {} })
}

beforeEach(() => {
  useExecutionStore.getState().reset()
})

describe('executionStore multi-job model', () => {
  it('keeps concurrent jobs fully isolated', () => {
    const store = useExecutionStore.getState()
    store.startJob('job_1', 'sess_a')
    store.startJob('job_2', 'sess_b')
    store.addLog('job_1', makeLog('line for job 1'))
    store.setStatus('job_2', 'running', 55, 'clustering')
    store.setResult('job_2', { success: true })

    const state = useExecutionStore.getState()
    expect(state.jobs['job_1'].logs.map((l) => l.message)).toEqual(['line for job 1'])
    expect(state.jobs['job_1'].status).toBe('running')
    expect(state.jobs['job_1'].percent).toBe(0)
    expect(state.jobs['job_1'].result).toBeNull()

    expect(state.jobs['job_2'].logs).toEqual([])
    expect(state.jobs['job_2'].percent).toBe(55)
    expect(state.jobs['job_2'].currentPhase).toBe('clustering')
    expect(state.jobs['job_2'].result).toEqual({ success: true })

    expect(state.activeJobIdBySession).toEqual({ sess_a: 'job_1', sess_b: 'job_2' })
    expect(state.jobs['job_1'].sessionId).toBe('sess_a')
    expect(state.jobs['job_2'].sessionId).toBe('sess_b')
  })

  it('deactivate clears only the session pointer and retains job data', () => {
    const store = useExecutionStore.getState()
    store.startJob('job_1', 'sess_a')
    store.addLog('job_1', makeLog('kept'))
    store.setResult('job_1', { success: true })

    useExecutionStore.getState().deactivate('sess_a')

    const state = useExecutionStore.getState()
    expect(selectActiveJobId(state, 'sess_a')).toBeNull()
    expect(selectActiveJob(state, 'sess_a')).toBeNull()
    // Runtime data survives deactivation.
    expect(state.jobs['job_1'].logs.map((l) => l.message)).toEqual(['kept'])
    expect(state.jobs['job_1'].result).toEqual({ success: true })

    // Re-pointing the session restores the view without data loss.
    useExecutionStore.getState().setActiveJob('sess_a', 'job_1')
    expect(selectActiveJob(useExecutionStore.getState(), 'sess_a')?.logs).toHaveLength(1)
  })

  it('removeJob drops runtime data and any pointers referencing it', () => {
    const store = useExecutionStore.getState()
    store.startJob('job_1', 'sess_a')
    store.startJob('job_2', 'sess_b')

    useExecutionStore.getState().removeJob('job_1')

    const state = useExecutionStore.getState()
    expect(state.jobs['job_1']).toBeUndefined()
    expect(state.activeJobIdBySession['sess_a']).toBeUndefined()
    expect(state.activeJobIdBySession['sess_b']).toBe('job_2')

    // Unknown ids are a no-op.
    useExecutionStore.getState().removeJob('job_1')
    expect(useExecutionStore.getState().jobs['job_2']).toBeDefined()
  })

  it('restoreJob keeps richer in-memory logs when the job already exists', () => {
    const store = useExecutionStore.getState()
    store.startJob('job_1', 'sess_a')
    store.addLog('job_1', makeLog('live line'))

    // Session reload rebuilds logs from the trace; those must not clobber the
    // live buffer accumulated via SSE.
    useExecutionStore
      .getState()
      .restoreJob('job_1', 'sess_a', [{ ...makeLog('trace line'), id: 'trace_1' }], 'running', 40, 'qc')

    const job = useExecutionStore.getState().jobs['job_1']
    expect(job.logs.map((l) => l.message)).toEqual(['live line'])
    expect(job.percent).toBe(40)
    expect(job.currentPhase).toBe('qc')
    expect(useExecutionStore.getState().activeJobIdBySession['sess_a']).toBe('job_1')
  })

  it('restoreJob seeds trace logs for a job with no local data', () => {
    useExecutionStore
      .getState()
      .restoreJob('job_1', 'sess_a', [{ ...makeLog('trace line'), id: 'trace_1' }], 'completed', 100)

    const job = useExecutionStore.getState().jobs['job_1']
    expect(job.logs.map((l) => l.message)).toEqual(['trace line'])
    expect(job.status).toBe('completed')
    expect(job.isConnected).toBe(false)
  })

  it('caps retained logs per job, leaving other jobs untouched', () => {
    const store = useExecutionStore.getState()
    store.startJob('job_1', 'sess_a')
    store.startJob('job_2', 'sess_b')
    store.addLog('job_2', makeLog('job 2 line'))

    const overflow = MAX_LOG_ENTRIES + 201
    for (let i = 0; i < overflow; i += 1) {
      useExecutionStore.getState().addLog('job_1', makeLog(`line ${i}`))
    }

    const state = useExecutionStore.getState()
    // Amortized truncation: once the buffer passes MAX+200 it is cut back to
    // MAX before the append, so it oscillates in (MAX, MAX+200].
    expect(state.jobs['job_1'].logs).toHaveLength(MAX_LOG_ENTRIES + 1)
    // The newest entries survive truncation.
    expect(state.jobs['job_1'].logs[0].message).toBe(`line ${overflow - (MAX_LOG_ENTRIES + 1)}`)
    expect(state.jobs['job_1'].logs[MAX_LOG_ENTRIES].message).toBe(`line ${overflow - 1}`)
    expect(state.jobs['job_2'].logs.map((l) => l.message)).toEqual(['job 2 line'])
  })

  it('evicts the oldest terminal jobs beyond the cap', () => {
    seedTerminalJobs(MAX_TERMINAL_JOBS + 1)
    // Trigger eviction by re-marking one job terminal.
    useExecutionStore.getState().setStatus(`job_${MAX_TERMINAL_JOBS}`, 'completed')

    const jobs = useExecutionStore.getState().jobs
    expect(jobs['job_0']).toBeUndefined()
    expect(Object.keys(jobs)).toHaveLength(MAX_TERMINAL_JOBS)
    expect(jobs[`job_${MAX_TERMINAL_JOBS}`]).toBeDefined()
  })

  it('never evicts a terminal job still referenced by a session pointer', () => {
    seedTerminalJobs(MAX_TERMINAL_JOBS + 1)
    // Keep the oldest job displayed in its session.
    useExecutionStore.setState({ activeJobIdBySession: { sess_0: 'job_0' } })
    useExecutionStore.getState().setStatus(`job_${MAX_TERMINAL_JOBS}`, 'completed')

    const jobs = useExecutionStore.getState().jobs
    expect(jobs['job_0']).toBeDefined()
    // The oldest unreferenced terminal job was evicted instead.
    expect(jobs['job_1']).toBeUndefined()
    expect(Object.keys(jobs)).toHaveLength(MAX_TERMINAL_JOBS)
  })

  it('ignores writes for unknown job ids', () => {
    const store = useExecutionStore.getState()
    store.addLog('ghost', makeLog('nope'))
    store.setStatus('ghost', 'running', 10)
    store.setConnected('ghost', true)
    store.setResult('ghost', { success: true })
    store.clearLogs('ghost')
    expect(useExecutionStore.getState().jobs).toEqual({})
  })

  it('reset wipes all jobs and pointers', () => {
    const store = useExecutionStore.getState()
    store.startJob('job_1', 'sess_a')
    store.startJob('job_2', 'sess_b')

    useExecutionStore.getState().reset()

    const state = useExecutionStore.getState()
    expect(state.jobs).toEqual({})
    expect(state.activeJobIdBySession).toEqual({})
  })
})
