import { useState } from 'react'
import { clsx } from 'clsx'
import { ReportList } from './ReportList'
import { ReportViewer } from './ReportViewer'

export function ReportPanel() {
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null)

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
        <div className="flex-1">
          <ReportViewer reportId={selectedReportId} onBack={() => setSelectedReportId(null)} />
        </div>
      )}
    </div>
  )
}
