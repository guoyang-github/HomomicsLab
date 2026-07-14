import { useState } from 'react'
import { clsx } from 'clsx'
import { ReportList } from '@/components/reports/ReportList'
import { ReportViewer } from '@/components/reports/ReportViewer'

interface ReportOverlayProps {
  initialReportId?: string
}

export function ReportOverlay({ initialReportId }: ReportOverlayProps) {
  const [selectedReportId, setSelectedReportId] = useState<string | null>(initialReportId || null)

  return (
    <div className="flex h-full overflow-hidden">
      <div
        className={clsx(
          'h-full border-r border-border bg-card transition-all',
          selectedReportId ? 'w-72 shrink-0' : 'w-full'
        )}
      >
        <ReportList
          onSelectReport={setSelectedReportId}
          selectedReportId={selectedReportId || undefined}
        />
      </div>
      {selectedReportId && (
        <div className="min-w-0 flex-1">
          <ReportViewer reportId={selectedReportId} onBack={() => setSelectedReportId(null)} />
        </div>
      )}
    </div>
  )
}
