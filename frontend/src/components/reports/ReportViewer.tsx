import { useState, useEffect, useRef } from 'react'
import { reportApi } from '@/services/api'
import type { ReportDetail } from '@/types/api'

interface ReportViewerProps {
  reportId: string
  onBack?: () => void
}

type ViewMode = 'html' | 'json' | 'steps'

export function ReportViewer({ reportId, onBack }: ReportViewerProps) {
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
    } catch (err) {
      setError('Failed to load report')
      console.error(err)
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
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
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
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Failed to download markdown:', err)
    }
  }

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      completed: 'bg-emerald-100 text-emerald-700',
      failed: 'bg-red-100 text-red-700',
      running: 'bg-amber-100 text-amber-700',
      pending: 'bg-slate-100 text-slate-600',
    }
    return styles[status] || 'bg-slate-100 text-slate-600'
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-sm text-slate-500">Loading report...</div>
      </div>
    )
  }

  if (error || !report) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2">
        <div className="text-sm text-red-500">{error || 'Report not found'}</div>
        {onBack && (
          <button
            onClick={onBack}
            className="rounded bg-primary px-3 py-1 text-xs text-white hover:bg-primary/90"
          >
            Back to List
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-2">
        <div className="flex items-center gap-3">
          {onBack && (
            <button
              onClick={onBack}
              className="rounded p-1 text-slate-500 hover:bg-slate-100"
              title="Back to list"
            >
              ←
            </button>
          )}
          <div>
            <h3 className="text-sm font-semibold text-slate-800">{report.title}</h3>
            <div className="text-xs text-slate-500">
              {report.metadata.project_name && `${report.metadata.project_name} · `}
              {report.metadata.analysis_type || 'Analysis'}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* View mode tabs */}
          <div className="flex rounded-lg bg-slate-100 p-0.5">
            {(['html', 'json', 'steps'] as ViewMode[]).map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                  viewMode === mode
                    ? 'bg-white text-slate-800 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                {mode === 'html' ? 'Report' : mode === 'json' ? 'JSON' : 'Steps'}
              </button>
            ))}
          </div>
          <div className="mx-1 h-4 w-px bg-slate-200" />
          <button
            onClick={handleDownloadHtml}
            className="rounded bg-primary px-2.5 py-1 text-xs text-white hover:bg-primary/90"
          >
            Download HTML
          </button>
          <button
            onClick={handleDownloadMarkdown}
            className="rounded border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-50"
          >
            Download MD
          </button>
        </div>
      </div>

      {/* Content */}
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
          <div className="h-full overflow-auto bg-slate-50 p-4">
            <pre className="rounded-lg bg-white p-4 text-xs leading-relaxed text-slate-700 shadow-sm">
              {JSON.stringify(report, null, 2)}
            </pre>
          </div>
        )}

        {viewMode === 'steps' && (
          <div className="h-full overflow-auto bg-slate-50 p-4">
            <div className="mx-auto max-w-2xl space-y-3">
              {report.analysis_steps.length === 0 && (
                <div className="text-center text-sm text-slate-500">No analysis steps recorded</div>
              )}
              {report.analysis_steps.map((step) => (
                <div
                  key={step.step_number}
                  className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs font-bold text-white">
                        {step.step_number}
                      </span>
                      <span className="text-sm font-medium text-slate-800">{step.name}</span>
                    </div>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${getStatusBadge(
                        step.status
                      )}`}
                    >
                      {step.status || 'unknown'}
                    </span>
                  </div>
                  {step.description && (
                    <p className="mt-2 text-xs text-slate-600">{step.description}</p>
                  )}
                  <div className="mt-2 flex items-center gap-4 text-xs text-slate-400">
                    {step.skill_id && <span>Skill: <code className="rounded bg-slate-100 px-1 py-0.5">{step.skill_id}</code></span>}
                    {step.duration_seconds !== null && (
                      <span>Duration: {step.duration_seconds.toFixed(1)}s</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
