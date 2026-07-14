import { describe, it, expect } from 'vitest'
import { formatActorLabel, groupSubagentLogs, subagentGroupKey } from './subagentLogs'
import type { LogEntry } from '@/stores/executionStore'

function log(partial: Partial<LogEntry> & { message: string }): LogEntry {
  return {
    id: `log_${partial.message}`,
    timestamp: '2026-07-14T10:00:00.000Z',
    level: 'info',
    ...partial,
  }
}

describe('subagentGroupKey', () => {
  it('keys by parentId and actor', () => {
    expect(subagentGroupKey({ actor: 'subagent:a', parentId: 'task-1' })).toBe('task-1::subagent:a')
  })

  it('tolerates a missing parentId', () => {
    expect(subagentGroupKey({ actor: 'subagent:a' })).toBe('::subagent:a')
  })
})

describe('formatActorLabel', () => {
  it('formats subagent actors with the skill id', () => {
    expect(formatActorLabel('subagent:celltypist')).toBe('🔬 subagent: celltypist')
    expect(formatActorLabel('subagent: celltypist')).toBe('🔬 subagent: celltypist')
  })

  it('falls back to the raw actor for other prefixes', () => {
    expect(formatActorLabel('worker:qc')).toBe('🔬 worker:qc')
  })
})

describe('groupSubagentLogs', () => {
  it('passes untagged (top-level) logs through flat and unchanged', () => {
    const logs = [log({ message: 'a' }), log({ message: 'b', level: 'stdout' })]
    const items = groupSubagentLogs(logs)
    expect(items).toEqual([
      { type: 'log', log: logs[0] },
      { type: 'log', log: logs[1] },
    ])
  })

  it('returns an empty list for no logs', () => {
    expect(groupSubagentLogs([])).toEqual([])
  })

  it('folds actor-tagged logs into a group at first-seen position, keeping flat order around it', () => {
    const top1 = log({ message: 'top-1' })
    const sub1 = log({ message: 'sub-1', actor: 'subagent:celltypist', parentId: 'task-1' })
    const top2 = log({ message: 'top-2' })
    const sub2 = log({ message: 'sub-2', actor: 'subagent:celltypist', parentId: 'task-1' })

    const items = groupSubagentLogs([top1, sub1, top2, sub2])

    expect(items).toHaveLength(3)
    expect(items[0]).toEqual({ type: 'log', log: top1 })
    expect(items[1].type).toBe('group')
    expect(items[2]).toEqual({ type: 'log', log: top2 })

    const group = items[1].type === 'group' ? items[1].group : null
    expect(group?.actor).toBe('subagent:celltypist')
    expect(group?.parentId).toBe('task-1')
    expect(group?.status).toBe('running')
    expect(group?.logs).toEqual([sub1, sub2])
  })

  it('keeps different actors and different parents in separate groups', () => {
    const a = log({ message: 'a', actor: 'subagent:x', parentId: 'task-1' })
    const b = log({ message: 'b', actor: 'subagent:y', parentId: 'task-1' })
    const c = log({ message: 'c', actor: 'subagent:x', parentId: 'task-2' })

    const items = groupSubagentLogs([a, b, c])
    const groups = items.filter((item) => item.type === 'group')

    expect(groups).toHaveLength(3)
    const keys = groups.map((item) => (item.type === 'group' ? item.group.key : ''))
    expect(keys).toEqual(['task-1::subagent:x', 'task-1::subagent:y', 'task-2::subagent:x'])
  })

  it('marks the group completed once a completed marker log arrives', () => {
    const items = groupSubagentLogs([
      log({ message: 'work', actor: 'subagent:celltypist', parentId: 'task-1' }),
      log({
        message: 'done',
        level: 'success',
        actor: 'subagent:celltypist',
        parentId: 'task-1',
        subStatus: 'completed',
      }),
    ])
    const group = items[0].type === 'group' ? items[0].group : null
    expect(group?.status).toBe('completed')
  })

  it('marks the group failed on a failed marker, and the latest marker wins', () => {
    const items = groupSubagentLogs([
      log({ message: 'm1', actor: 'subagent:x', subStatus: 'completed' }),
      log({ message: 'm2', level: 'error', actor: 'subagent:x', subStatus: 'failed' }),
    ])
    const group = items[0].type === 'group' ? items[0].group : null
    expect(group?.status).toBe('failed')
  })

  it('stays running when no terminal marker exists even with error-level lines', () => {
    const items = groupSubagentLogs([
      log({ message: 'boom', level: 'error', actor: 'subagent:x', parentId: 'task-1' }),
    ])
    const group = items[0].type === 'group' ? items[0].group : null
    expect(group?.status).toBe('running')
  })
})
