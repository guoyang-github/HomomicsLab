import type { LogEntry } from '@/stores/executionStore'

export type SubagentStatus = 'running' | 'completed' | 'failed'

export interface SubagentLogGroup {
  /** Stable identity: `${parentId}::${actor}`. */
  key: string
  actor: string
  parentId?: string
  /** Derived from the latest terminal marker log; 'running' until then. */
  status: SubagentStatus
  logs: LogEntry[]
}

export type LogTreeItem =
  | { type: 'log'; log: LogEntry }
  | { type: 'group'; group: SubagentLogGroup }

export function subagentGroupKey(log: { actor?: string; parentId?: string }): string {
  return `${log.parentId ?? ''}::${log.actor ?? ''}`
}

/**
 * Human-facing label for a sub-executor actor string.
 * "subagent:celltypist" -> "🔬 subagent: celltypist".
 */
export function formatActorLabel(actor: string): string {
  const match = /^subagent[:：]\s*(.+)$/.exec(actor)
  if (match) return `🔬 subagent: ${match[1]}`
  return `🔬 ${actor}`
}

/**
 * Turn the flat execution log stream into a render tree: entries tagged with
 * an `actor` (sub-executor events) are folded into a group keyed by
 * (parentId, actor), positioned at the group's first occurrence. Untagged
 * entries keep their flat order, so legacy top-level events render unchanged.
 */
export function groupSubagentLogs(logs: LogEntry[]): LogTreeItem[] {
  const items: LogTreeItem[] = []
  const groups = new Map<string, SubagentLogGroup>()

  for (const log of logs) {
    if (!log.actor) {
      items.push({ type: 'log', log })
      continue
    }
    const key = subagentGroupKey(log)
    let group = groups.get(key)
    if (!group) {
      group = { key, actor: log.actor, parentId: log.parentId, status: 'running', logs: [] }
      groups.set(key, group)
      items.push({ type: 'group', group })
    }
    group.logs.push(log)
    if (log.subStatus) {
      group.status = log.subStatus
    }
  }

  return items
}
