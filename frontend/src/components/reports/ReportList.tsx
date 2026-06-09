import { useState, useEffect } from 'react'
import { reportApi } from '@/services/api'
import type { ReportSummary } from '@/types/api'

interface ReportListProps {
  onSelectReport: (reportId: string) => void
  selectedReportId?: string
}

export function ReportList({ onSelectReport, selectedReportId }: ReportListProps) {
  const [reports, setReports] = useState<ReportSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    loadReports()
  }, [])

  const loadReports = async () => {
    try {
      setLoading(true)
      const response = await reportApi.listReports()
      setReports(response.data)
      setError('')
    } catch (err) {
      setError('Failed to load reports')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (stepCount: number) => {
    if (stepCount === 0) return 'bg-slate-100 text-slate-500'
    return 'bg-emerald-100 text-emerald-700'
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-sm text-slate-500">Loading reports...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-4">
        <div className="text-sm text-red-500">{error}</div>
        <button
          onClick={loadReports}
          className="rounded bg-primary px-3 py-1 text-xs text-white hover:bg-primary/90"
        >
          Retry
        </button>
      </div>
    )
  }

  if (reports.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-4 text-center">
        <div className="mb-2 text-3xl">📊</div>
        <div className="text-sm font-medium text-slate-700">No reports yet</div>
        <div className="mt-1 text-xs text-slate-500">
          Run an analysis pipeline to generate reports
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="border-b border-slate-200 bg-slate-50 px-3 py-2">
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Reports ({reports.length})
        </div>
      </div>
      <div className="divide-y divide-slate-100">
        {reports.map((report) => (
          <button
            key={report.id}
            onClick={() => onSelectReport(report.id)}
            className={`w-full px-3 py-3 text-left transition-colors hover:bg-slate-50 ${
              selectedReportId === report.id ? 'bg-blue-50 ring-1 ring-inset ring-blue-200' : ''
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-slate-800">
                  {report.title}
                </div>
                {report.project_name && (
                  <div className="mt-0.5 truncate text-xs text-slate-500">
                    {report.project_name}
                  </div>
                )}
              </div>
              <span
                className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${getStatusColor(
                  report.step_count
                )}`}
              >
                {report.step_count} steps
              </span>
            </div>
            <div className="mt-1.5 flex items-center gap-3 text-xs text-slate-400">
              <span>{report.analysis_type || 'Analysis'}</span>
              <span>·</span>
              <span>{new Date(report.created_at).toLocaleDateString()}</span>
              {report.section_count > 0 && (
                <>
                  <span>·</span>
                  <span>{report.section_count} sections</span>
                </>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
