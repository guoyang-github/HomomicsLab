import { describe, it, expect } from 'vitest'
import { buildPhaseTasks, domainFromMessages, resolveWorkflowAvailability } from './workflowPhases'
import type { WorkflowSkeleton } from '@/stores/executionStore'
import type { ChatMessage } from '@/types/chat'

const skeleton: WorkflowSkeleton = {
  domain: 'single-cell-transcriptomics',
  phases: [
    { phase_type: 'qc', name: 'Quality Control', skipped: false },
    { phase_type: 'doublet', name: 'Doublet Detection', skipped: true },
    { phase_type: 'normalization', name: 'Normalization', skipped: false },
    { phase_type: 'clustering', name: 'Clustering', skipped: false },
  ],
}

describe('buildPhaseTasks', () => {
  it('returns null without a skeleton', () => {
    expect(buildPhaseTasks(null, {})).toBeNull()
    expect(buildPhaseTasks(undefined, undefined)).toBeNull()
  })

  it('drops skipped phases and chains the rest serially', () => {
    const tasks = buildPhaseTasks(skeleton, {})!
    expect(tasks.map((t) => t.id)).toEqual(['qc', 'normalization', 'clustering'])
    expect(tasks.map((t) => t.dependencies)).toEqual([[], ['qc'], ['normalization']])
    expect(tasks.every((t) => t.fromPhase)).toBe(true)
    expect(tasks[0].name).toBe('Quality Control')
  })

  it('maps reported phase states and defaults unreported phases to pending', () => {
    const tasks = buildPhaseTasks(skeleton, {
      qc: { status: 'completed', updatedAt: 1 },
      normalization: { status: 'running', updatedAt: 2 },
    })!
    expect(tasks.map((t) => t.status)).toEqual(['completed', 'running', 'pending'])
  })
})

function todoMessage(domain: unknown, via: 'content' | 'metadata' | 'plan' = 'metadata'): ChatMessage {
  if (via === 'metadata') {
    return {
      id: 'm1',
      type: 'todo_list',
      content: { text: '', tasks: [] },
      sender: 'agent',
      timestamp: new Date().toISOString(),
      metadata: { domain: domain as string },
    }
  }
  if (via === 'plan') {
    return {
      id: 'm1',
      type: 'execution_plan',
      content: { plan_id: 'p1', response_text: '', tasks: [], plan: { domain } },
      sender: 'agent',
      timestamp: new Date().toISOString(),
    }
  }
  return {
    id: 'm1',
    type: 'todo_list',
    content: { text: '', tasks: [], domain },
    sender: 'agent',
    timestamp: new Date().toISOString(),
  }
}

describe('domainFromMessages', () => {
  it('reads the domain from metadata, content or plan payloads', () => {
    expect(domainFromMessages([todoMessage('genomics')])).toBe('genomics')
    expect(domainFromMessages([todoMessage('genomics', 'content')])).toBe('genomics')
    expect(domainFromMessages([todoMessage('genomics', 'plan')])).toBe('genomics')
  })

  it('prefers the latest message and ignores unrelated types', () => {
    const older = todoMessage('genomics')
    const newer = { ...todoMessage('generic'), id: 'm2' }
    expect(domainFromMessages([older, newer])).toBe('generic')
    const textMsg: ChatMessage = {
      id: 'm3',
      type: 'text',
      content: 'hello',
      sender: 'agent',
      timestamp: new Date().toISOString(),
      metadata: { domain: 'genomics' },
    }
    expect(domainFromMessages([textMsg])).toBeNull()
  })

  it('returns null when nothing carries a domain', () => {
    expect(domainFromMessages([])).toBeNull()
    expect(domainFromMessages([todoMessage(undefined)])).toBeNull()
  })
})

describe('resolveWorkflowAvailability', () => {
  const jobWithSkeleton = {
    workflowSkeleton: skeleton,
  } as any

  it('is domain when the active job has a skeleton', () => {
    expect(
      resolveWorkflowAvailability({ job: jobWithSkeleton, messages: [todoMessage('generic')], hasTaskTree: false })
    ).toBe('domain')
  })

  it('is generic on an explicit generic hint and domain on a named domain', () => {
    expect(resolveWorkflowAvailability({ job: null, messages: [todoMessage('generic')], hasTaskTree: true })).toBe(
      'generic'
    )
    expect(resolveWorkflowAvailability({ job: null, messages: [todoMessage('genomics')], hasTaskTree: true })).toBe(
      'domain'
    )
  })

  it('falls back to legacy with a task tree and generic without anything', () => {
    expect(resolveWorkflowAvailability({ job: null, messages: [], hasTaskTree: true })).toBe('legacy')
    expect(resolveWorkflowAvailability({ job: null, messages: [], hasTaskTree: false })).toBe('generic')
  })
})
