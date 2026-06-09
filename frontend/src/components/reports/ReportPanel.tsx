import { useState } from 'react'
import { ReportList } from './ReportList'
import { ReportViewer } from './ReportViewer'

export function ReportPanel() {
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null)

  return (
    <div className="h-full">
      {selectedReportId ? (
        <ReportViewer
          reportId={selectedReportId}
          onBack={() => setSelectedReportId(null)}
        />
      ) : (
        <ReportList
          onSelectReport={setSelectedReportId}
          selectedReportId={selectedReportId || undefined}
        />
      )}
    </div>
  )
}
