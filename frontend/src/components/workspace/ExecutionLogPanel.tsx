import { useRef, useEffect, useState } from 'react'
import { clsx } from 'clsx'
import { Terminal, ChevronUp, ChevronDown, Trash2, Download, Activity } from 'lucide-react'
import { useExecutionStore } from '@/stores/executionStore'
import { Button, Badge } from '@/components/ui'
import { useTranslation } from '@/i18n'

export function ExecutionLogPanel() {
  const { t } = useTranslation()
  const logs = useExecutionStore((state) => state.logs)
  const status = useExecutionStore((state) => state.status)
  const isConnected = useExecutionStore((state) => state.isConnected)
  const clearLogs = useExecutionStore((state) => state.clearLogs)
  const [expanded, setExpanded] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

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
              {logs.map((log) => (
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
                      log.level === 'info' && 'text-primary'
                    )}
                  >
                    {log.level}
                  </span>
                  <span className={clsx('break-all', log.level === 'error' && 'text-error', log.level === 'stderr' && 'text-error')}>
                    {log.message}
                  </span>
                  {log.taskId && <span className="shrink-0 text-muted-foreground">[{log.taskId}]</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
