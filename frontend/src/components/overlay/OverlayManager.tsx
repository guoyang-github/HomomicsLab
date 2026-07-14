import { useOverlayStore, type OverlayType } from '@/stores/overlayStore'
import { useTranslation } from '@/i18n'
import { FullscreenOverlay } from './FullscreenOverlay'
import { ReportOverlay } from './ReportOverlay'
import { FigureOverlay } from './FigureOverlay'
import { WorkflowOverlay } from './WorkflowOverlay'

const TITLES: Record<NonNullable<OverlayType>, string> = {
  report: 'overlay.reportTitle',
  figure: 'overlay.figureTitle',
  workflow: 'overlay.workflowTitle',
}

export function OverlayManager() {
  const { t } = useTranslation()
  const { open, params, closeOverlay } = useOverlayStore()

  if (!open) return null

  return (
    <FullscreenOverlay title={t(TITLES[open])} onClose={closeOverlay}>
      {open === 'report' && <ReportOverlay initialReportId={params?.reportId as string | undefined} />}
      {open === 'figure' && <FigureOverlay params={params} />}
      {open === 'workflow' && <WorkflowOverlay />}
    </FullscreenOverlay>
  )
}
