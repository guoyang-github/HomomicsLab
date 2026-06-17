import { useState, useEffect, useRef } from 'react'
import { clsx } from 'clsx'
import { ArrowLeft, Download, FileCode, List, FileText } from 'lucide-react'
import { reportApi } from '@/services/api'
import { useTranslation } from '@/i18n'
import type { ReportDetail } from '@/types/api'
import { Button, Badge, Card, CardHeader, CardTitle, CardContent } from '@/components/ui'

interface ReportViewerProps {
  reportId: string
  onBack?: () => void
}

type ViewMode = 'html' | 'json' | 'steps'

export function ReportViewer({ reportId, onBack }: ReportViewerProps) {
  const { t } = useTranslation()
  const [report, setReport] = useState<ReportDetail | null>(null)
  const [htmlContent, setHtmlContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [viewMode, setViewMode] = useState<ViewMode>('html')
  const iframeRef = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    loadReport()
  }, [reportId])

  const loadReport = async () => {
    try {
      setLoading(true)
      const [detailRes, htmlRes] = await Promise.all([
        reportApi.getReport(reportId),
        reportApi.exportHtml(reportId),
      ])
      setReport(detailRes.data)
      setHtmlContent(htmlRes.data.html)
      setError('')
    } catch (err: any) {
      setError(err?.response?.data?.detail || t('reports.loadFailed'))
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadHtml = () => {
    if (!htmlContent || !report) return
    const blob = new Blob([htmlContent], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${report.title.replace(/\s+/g, '_')}.html`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleDownloadMarkdown = async () => {
    if (!report) return
    try {
      const res = await reportApi.exportMarkdown(reportId)
      const blob = new Blob([res.data.markdown], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${report.title.replace(/\s+/g, '_')}.md`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Failed to download markdown:', err)
    }
  }

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      completed: 'bg-success/10 text-success',
      failed: 'bg-error/10 text-error',
      running: 'bg-warning/10 text-warning',
      pending: 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400',
    }
    return styles[status] || styles.pending
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (error || !report) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2">
        <div className="text-sm text-error">{error || t('reports.notFound')}</div>
        {onBack && (
          <Button onClick={onBack} size="sm">
            <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
            {t('reports.backToList')}
          </Button>
        )}
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border bg-card px-4 py-3">
        <div className="flex items-center gap-3">
          {onBack && (
            <Button variant="ghost" size="icon" onClick={onBack} title={t('reports.backToList')}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
          )}
          <div>
            <h3 className="text-sm font-semibold text-foreground">{report.title}</h3>
            <div className="text-xs text-muted-foreground">
              {report.metadata.project_name && `${report.metadata.project_name} · `}
              {report.metadata.analysis_type || t('reports.analysis')}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="hidden items-center gap-1 rounded-lg border border-border p-0.5 sm:flex">
            {[
              { mode: 'html' as ViewMode, label: t('reports.tabReport'), icon: FileText },
              { mode: 'json' as ViewMode, label: 'JSON', icon: FileCode },
              { mode: 'steps' as ViewMode, label: t('reports.tabSteps'), icon: List },
            ].map(({ mode, label, icon: Icon }) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={clsx(
                  'flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors',
                  viewMode === mode
                    ? 'bg-primary text-white'
                    : 'text-muted-foreground hover:bg-muted'
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </button>
            ))}
          </div>
          <Button size="sm" onClick={handleDownloadHtml}>
            <Download className="mr-1.5 h-3.5 w-3.5" />
            HTML
          </Button>
          <Button size="sm" variant="outline" onClick={handleDownloadMarkdown}>
            MD
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        {viewMode === 'html' && (
          <iframe
            ref={iframeRef}
            srcDoc={htmlContent}
            className="h-full w-full border-0"
            sandbox="allow-same-origin"
            title={`Report: ${report.title}`}
          />
        )}

        {viewMode === 'json' && (
          <div className="h-full overflow-auto bg-muted/30 p-4">
            <pre className="rounded-xl border border-border bg-card p-4 text-xs leading-relaxed shadow-card">
              {JSON.stringify(report, null, 2)}
            </pre>
          </div>
        )}

        {viewMode === 'steps' && (
          <div className="h-full overflow-auto bg-muted/30 p-4">
            <div className="mx-auto max-w-3xl space-y-3">
              {report.analysis_steps.length === 0 && (
                <div className="text-center text-sm text-muted-foreground">{t('reports.noSteps')}</div>
              )}
              {report.analysis_steps.map((step) => (
                <Card key={step.step_number}>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-bold text-white">
                          {step.step_number}
                        </span>
                        <CardTitle className="text-sm">{step.name}</CardTitle>
                      </div>
                      <Badge className={getStatusBadge(step.status)} size="sm">
                        {step.status || 'unknown'}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {step.description && (
                      <p className="text-sm text-muted-foreground">{step.description}</p>
                    )}
                    <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                      {step.skill_id && (
                        <span>
                          Skill: <code className="rounded bg-muted px-1 py-0.5">{step.skill_id}</code>
                        </span>
                      )}
                      {step.duration_seconds !== null && (
                        <span>{t('reports.durationLabel', { seconds: step.duration_seconds.toFixed(1) })}</span>
                      )}
                      {step.started_at && (
                        <span>{t('reports.startedAtLabel', { datetime: new Date(step.started_at).toLocaleString() })}</span>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
