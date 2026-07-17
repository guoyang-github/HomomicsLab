import { useRef, useEffect, useState, useMemo } from 'react'
import { clsx } from 'clsx'
import { Terminal, ChevronUp, ChevronDown, ChevronRight, Trash2, Download, Activity } from 'lucide-react'
import { useExecutionStore } from '@/stores/executionStore'
import type { LogEntry } from '@/stores/executionStore'
import { useActiveExecutionJob } from '@/hooks/useActiveExecutionJob'
import { Button, Badge } from '@/components/ui'
import { useTranslation } from '@/i18n'
import { formatActorLabel, groupSubagentLogs } from '@/utils/subagentLogs'
import type { SubagentLogGroup, SubagentStatus } from '@/utils/subagentLogs'

interface Props {
  /** Card-style variant for embedding above the chat input. Auto-expands
   * while running and collapses to a one-line summary on terminal states. */
  compact?: boolean
}

/** Stable empty buffer so a jobless panel does not re-render on every store change. */
const NO_LOGS: LogEntry[] = []

export function ExecutionLogPanel({ compact = false }: Props) {
  const { t } = useTranslation()
  // Renders the job attached to the current session; other sessions' jobs
  // keep their logs in the store and reappear here on session switch.
  const { jobId, job } = useActiveExecutionJob()
  const logs = job?.logs ?? NO_LOGS
  const status = job?.status ?? 'idle'
  const isConnected = job?.isConnected ?? false
  const clearLogs = useExecutionStore((state) => state.clearLogs)
  const [expanded, setExpanded] = useState(false)
  const [userCollapsed, setUserCollapsed] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-expand the compact embedded panel while a job is running so users
  // can see live execution output without an extra click. If the user has
  // explicitly collapsed the panel, respect that choice until they expand it
  // again.
  useEffect(() => {
    if (compact && status === 'running' && !userCollapsed && !expanded) {
      setExpanded(true)
    }
  }, [compact, status, userCollapsed, expanded])

  const items = useMemo(() => groupSubagentLogs(logs), [logs])
  // Per-group open state; groups default to expanded while running and
  // collapse once the sub-executor reaches a terminal state.
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({})
  const isGroupOpen = (group: SubagentLogGroup) =>
    openGroups[group.key] ?? group.status === 'running'
  const toggleGroup = (group: SubagentLogGroup) =>
    setOpenGroups((prev) => ({ ...prev, [group.key]: !isGroupOpen(group) }))

  const isTerminal = status === 'completed' || status === 'failed' || status === 'aborted'
  const stepCount = useMemo(
    () => logs.filter((log) => log.level === 'tool' || log.level === 'success').length || logs.length,
    [logs]
  )

  useEffect(() => {
    if (expanded) {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [logs, expanded])

  const downloadLogs = () => {
    const text = logs
      .map((log) => `[${new Date(log.timestamp).toLocaleTimeString()}] [${log.level.toUpperCase()}] ${log.message}`)
      .join('\n')
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `execution-logs-${Date.now()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const renderStatusBadge = () => {
    switch (status) {
      case 'idle':
        return <Badge variant="secondary">{t('executionLog.idle')}</Badge>
      case 'running':
        return (
          <Badge variant="info">
            <Activity className="mr-1 h-3 w-3 animate-pulse" />
            {t('executionLog.running')}
          </Badge>
        )
      case 'completed':
        return <Badge variant="success">{t('executionLog.completed')}</Badge>
      case 'failed':
        return <Badge variant="error">{t('executionLog.failed')}</Badge>
      case 'aborted':
        return <Badge variant="warning">{t('executionLog.aborted')}</Badge>
      default:
        return null
    }
  }

  const renderGroupBadge = (groupStatus: SubagentStatus) => {
    switch (groupStatus) {
      case 'completed':
        return <Badge variant="success">{t('executionLog.completed')}</Badge>
      case 'failed':
        return <Badge variant="error">{t('executionLog.failed')}</Badge>
      default:
        return (
          <Badge variant="info">
            <Activity className="mr-1 h-3 w-3 animate-pulse" />
            {t('executionLog.running')}
          </Badge>
        )
    }
  }

  const renderLogLine = (log: LogEntry) => (
    <div key={log.id} className="flex gap-2">
      <span className="shrink-0 text-muted-foreground">
        {new Date(log.timestamp).toLocaleTimeString()}
      </span>
      <span
        className={clsx(
          'shrink-0 font-bold uppercase',
          log.level === 'error' && 'text-error',
          log.level === 'stderr' && 'text-error',
          log.level === 'stdout' && 'text-foreground',
          log.level === 'success' && 'text-success',
          log.level === 'info' && 'text-primary',
          log.level === 'warning' && 'text-warning',
          log.level === 'tool' && 'text-primary',
          log.level === 'artifact' && 'text-success'
        )}
      >
        {log.level}
      </span>
      <span className={clsx('break-all', log.level === 'error' && 'text-error', log.level === 'stderr' && 'text-error')}>
        {log.message}
      </span>
      {log.taskId && <span className="shrink-0 text-muted-foreground">[{log.taskId}]</span>}
    </div>
  )

  const renderGroup = (group: SubagentLogGroup) => {
    const open = isGroupOpen(group)
    return (
      <div key={group.key} className="rounded border border-border-faint bg-surface-2/40">
        <button
          type="button"
          onClick={() => toggleGroup(group)}
          aria-expanded={open}
          className="flex w-full items-center gap-1.5 px-2 py-1 text-left"
        >
          {open ? (
            <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
          )}
          <span className="flex-1 truncate font-medium text-foreground">
            {formatActorLabel(group.actor)}
          </span>
          {renderGroupBadge(group.status)}
        </button>
        {open && (
          <div className="space-y-1 border-t border-border/60 py-1 pl-6 pr-2">
            {group.logs.map(renderLogLine)}
          </div>
        )}
      </div>
    )
  }

  return (
    <div
      className={clsx(
        'bg-surface transition-all duration-200',
        compact
          ? 'overflow-hidden rounded-xl border border-border-faint shadow-sm'
          : clsx('border-t border-border-faint', expanded ? 'h-64' : 'h-10')
      )}
    >
      <div
        className={clsx(
          'flex h-10 items-center justify-between px-4',
          (!compact || expanded) && 'border-b border-border'
        )}
      >
        <div className="flex min-w-0 items-center gap-3">
          <Terminal className="h-4 w-4 shrink-0 text-muted-foreground" />
          <span className="shrink-0 text-xs font-medium text-foreground">{t('executionLog.title')}</span>
          {renderStatusBadge()}
          {compact && !expanded && isTerminal && (
            <span className="truncate text-xs text-muted-foreground">
              {t('executionLog.finishedSummary', { count: stepCount })}
            </span>
          )}
          {isConnected && (
            <span className="flex h-2 w-2 shrink-0 rounded-full bg-success animate-pulse" />
          )}
        </div>
        <div className="flex items-center gap-1">
          {expanded && (
            <>
              <Button variant="ghost" size="icon" onClick={downloadLogs} title={t('executionLog.download')}>
                <Download className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => jobId && clearLogs(jobId)}
                title={t('executionLog.clear')}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => {
              const next = !expanded
              setExpanded(next)
              setUserCollapsed(!next)
            }}
            title={expanded ? t('executionLog.collapse') : t('executionLog.expand')}
          >
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      {expanded && (
        <div
          ref={scrollRef}
          className={clsx(
            'overflow-y-auto p-3 font-mono text-xs',
            compact ? 'max-h-64' : 'h-[216px]'
          )}
        >
          {logs.length === 0 ? (
            <div
              className={clsx(
                'flex items-center justify-center text-muted-foreground',
                compact ? 'h-16' : 'h-full'
              )}
            >
              {t('executionLog.empty')}
            </div>
          ) : (
            <div className="space-y-1">
              {items.map((item) =>
                item.type === 'log' ? renderLogLine(item.log) : renderGroup(item.group)
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
