import { useState, useEffect } from 'react'
import { clsx } from 'clsx'
import { FileText, RefreshCw } from 'lucide-react'
import { reportApi } from '@/services/api'
import type { ReportSummary } from '@/types/api'
import { Button, Badge, EmptyState } from '@/components/ui'

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
    } catch (err: any) {
      setError(err?.response?.data?.detail || '加载报告失败')
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (stepCount: number) => {
    if (stepCount === 0) return 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400'
    return 'bg-success/10 text-success'
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-4">
        <p className="text-sm text-error">{error}</p>
        <Button onClick={loadReports} size="sm">
          <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
          重试
        </Button>
      </div>
    )
  }

  if (reports.length === 0) {
    return (
      <EmptyState
        icon={FileText}
        title="暂无报告"
        description="运行分析流程以生成报告"
        action={{ label: '刷新', onClick: loadReports }}
      />
    )
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="border-b border-border bg-muted/50 px-4 py-3">
        <div className="text-sm font-semibold text-foreground">报告 ({reports.length})</div>
      </div>
      <div className="divide-y divide-border">
        {reports.map((report) => (
          <button
            key={report.id}
            onClick={() => onSelectReport(report.id)}
            className={clsx(
              'w-full px-4 py-3 text-left transition-colors hover:bg-muted/50',
              selectedReportId === report.id && 'bg-primary/5 ring-1 ring-inset ring-primary/20'
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-foreground">{report.title}</div>
                {report.project_name && (
                  <div className="mt-0.5 truncate text-xs text-muted-foreground">{report.project_name}</div>
                )}
              </div>
              <Badge className={getStatusColor(report.step_count)} size="sm">
                {report.step_count} 步骤
              </Badge>
            </div>
            <div className="mt-1.5 flex items-center gap-3 text-xs text-muted-foreground">
              <span>{report.analysis_type || '分析'}</span>
              <span>·</span>
              <span>{new Date(report.created_at).toLocaleDateString()}</span>
              {report.section_count > 0 && (
                <>
                  <span>·</span>
                  <span>{report.section_count} 章节</span>
                </>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
