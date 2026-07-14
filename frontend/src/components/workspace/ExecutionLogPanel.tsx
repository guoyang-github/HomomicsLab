import { useRef, useEffect, useState, useMemo } from 'react'
import { clsx } from 'clsx'
import { Terminal, ChevronUp, ChevronDown, ChevronRight, Trash2, Download, Activity } from 'lucide-react'
import { useExecutionStore } from '@/stores/executionStore'
import type { LogEntry } from '@/stores/executionStore'
import { Button, Badge } from '@/components/ui'
import { useTranslation } from '@/i18n'
import { formatActorLabel, groupSubagentLogs } from '@/utils/subagentLogs'
import type { SubagentLogGroup, SubagentStatus } from '@/utils/subagentLogs'

export function ExecutionLogPanel() {
  const { t } = useTranslation()
  const logs = useExecutionStore((state) => state.logs)
  const status = useExecutionStore((state) => state.status)
  const isConnected = useExecutionStore((state) => state.isConnected)
  const clearLogs = useExecutionStore((state) => state.clearLogs)
  const [expanded, setExpanded] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  const items = useMemo(() => groupSubagentLogs(logs), [logs])
  // Per-group open state; groups default to expanded while running and
  // collapse once the sub-executor reaches a terminal state.
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({})
  const isGroupOpen = (group: SubagentLogGroup) =>
    openGroups[group.key] ?? group.status === 'running'
  const toggleGroup = (group: SubagentLogGroup) =>
    setOpenGroups((prev) => ({ ...prev, [group.key]: !isGroupOpen(group) }))

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
      <div key={group.key} className="rounded border border-border bg-muted/20">
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
        'border-t border-border bg-card transition-all duration-200',
        expanded ? 'h-64' : 'h-10'
      )}
    >
      <div className="flex h-10 items-center justify-between border-b border-border px-4">
        <div className="flex items-center gap-3">
          <Terminal className="h-4 w-4 text-muted-foreground" />
          <span className="text-xs font-medium text-foreground">{t('executionLog.title')}</span>
          {renderStatusBadge()}
          {isConnected && (
            <span className="flex h-2 w-2 rounded-full bg-success animate-pulse" />
          )}
        </div>
        <div className="flex items-center gap-1">
          {expanded && (
            <>
              <Button variant="ghost" size="icon" onClick={downloadLogs} title={t('executionLog.download')}>
                <Download className="h-3.5 w-3.5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={clearLogs} title={t('executionLog.clear')}>
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </>
          )}
          <Button variant="ghost" size="icon" onClick={() => setExpanded((e) => !e)} title={expanded ? t('executionLog.collapse') : t('executionLog.expand')}>
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      {expanded && (
        <div ref={scrollRef} className="h-[216px] overflow-y-auto p-3 font-mono text-xs">
          {logs.length === 0 ? (
            <div className="flex h-full items-center justify-center text-muted-foreground">
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
