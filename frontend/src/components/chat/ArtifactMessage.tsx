import { lazy, Suspense, useState } from 'react'
import {
  BarChart3,
  Download,
  Eye,
  FileJson2,
  FileText,
  Globe,
  Image as ImageIcon,
  Maximize2,
  Table2,
} from 'lucide-react'
import { clsx } from 'clsx'
import { ArtifactRenderer, type Artifact } from '@/components/artifacts'
import { artifactUrl, downloadName } from '@/components/artifacts/renderers'
import { PlotChart } from '@/components/shared/PlotChart'
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from '@/components/ui/shadcn/dialog'
import { useProjectStore } from '@/stores/projectStore'
import { useOverlayStore } from '@/stores/overlayStore'
import { useTranslation } from '@/i18n'
import type { PlotDataRequest } from '@/types/api'

const Plot = lazy(() => import('react-plotly.js'))

export interface ArtifactMessageContent {
  artifacts?: Artifact[]
  artifact?: Artifact
}

interface Props {
  content: Artifact | ArtifactMessageContent
}

function normalizeArtifacts(content: Artifact | ArtifactMessageContent): Artifact[] {
  const c = content as ArtifactMessageContent
  if (Array.isArray(c.artifacts) && c.artifacts.length > 0) return c.artifacts
  if (c.artifact && typeof c.artifact === 'object') return [c.artifact]
  return [content as Artifact]
}

function kindIcon(kind: string) {
  switch (kind) {
    case 'image':
      return ImageIcon
    case 'table':
      return Table2
    case 'html':
      return Globe
    case 'json':
      return FileJson2
    case 'plotly':
      return BarChart3
    default:
      return FileText
  }
}

function isPlotlyFigure(data: unknown): data is { data: unknown[]; layout?: Record<string, unknown> } {
  return (
    typeof data === 'object' &&
    data !== null &&
    Array.isArray((data as Record<string, unknown>).data)
  )
}

function PlotlyBody({ artifact }: { artifact: Artifact }) {
  const { t } = useTranslation()
  // Ready-made figure JSON renders inline; a plot_type spec goes through the
  // existing PlotChart (backend viz API) path.
  if (isPlotlyFigure(artifact.data)) {
    return (
      <div className="h-[420px] w-full">
        <Suspense
          fallback={
            <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
              {t('common.loading')}…
            </div>
          }
        >
          <Plot
            data={artifact.data.data as Plotly.Data[]}
            layout={{ ...artifact.data.layout, autosize: true }}
            config={{
              responsive: true,
              displayModeBar: true,
              displaylogo: false,
              modeBarButtonsToRemove: ['lasso2d', 'select2d'],
            }}
            style={{ width: '100%', height: '100%' }}
            useResizeHandler
          />
        </Suspense>
      </div>
    )
  }
  const spec = artifact.data as Record<string, unknown> | undefined
  const plotType = (artifact as Record<string, unknown>).plot_type ?? spec?.plot_type
  if (typeof plotType === 'string') {
    const request: PlotDataRequest = {
      plot_type: plotType as PlotDataRequest['plot_type'],
      data: (spec?.data as Record<string, unknown>) ?? {},
      title: artifact.name,
      width: 700,
      height: 450,
    }
    return <PlotChart request={request} className="w-full" />
  }
  return <ArtifactRenderer artifact={{ ...artifact, kind: 'json' }} />
}

function ArtifactCard({ artifact, projectId }: { artifact: Artifact; projectId?: string }) {
  const { t } = useTranslation()
  const openReport = useOverlayStore((state) => state.openReport)
  const [fullscreen, setFullscreen] = useState(false)
  const kind = String(artifact.kind || 'file')
  const Icon = kindIcon(kind)
  const name = downloadName(artifact)
  const url = artifactUrl(projectId, artifact)
  const isHtml = kind === 'html'
  const reportId = (artifact as unknown as Record<string, unknown>).report_id as string | undefined

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-3 py-1.5 text-xs">
        <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span className="flex-1 truncate font-medium text-foreground" title={name}>
          {name || t('artifact.untitled')}
        </span>
        <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-2xs uppercase text-muted-foreground">
          {kind}
        </span>
        {reportId && (
          <button
            type="button"
            onClick={() => openReport({ reportId })}
            className="inline-flex shrink-0 items-center gap-1 rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            title={t('message.viewReport')}
          >
            <Eye className="h-3.5 w-3.5" />
          </button>
        )}
        {isHtml && (
          <button
            type="button"
            onClick={() => setFullscreen(true)}
            className="inline-flex shrink-0 items-center gap-1 rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            title={t('artifact.expand')}
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </button>
        )}
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            download
            className="inline-flex shrink-0 items-center rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            title={t('common.download')}
          >
            <Download className="h-3.5 w-3.5" />
          </a>
        )}
      </div>
      <div className={clsx('p-2', kind === 'table' && 'p-0')}>
        {kind === 'plotly' ? (
          <PlotlyBody artifact={artifact} />
        ) : (
          <ArtifactRenderer artifact={artifact} projectId={projectId} />
        )}
      </div>

      {isHtml && (
        <Dialog open={fullscreen} onOpenChange={setFullscreen}>
          <DialogContent className="flex h-[86vh] w-[92vw] max-w-[92vw] flex-col">
            <DialogTitle className="truncate pr-8 text-sm">{name}</DialogTitle>
            {url ? (
              <iframe
                src={url}
                title={name}
                sandbox=""
                className="min-h-0 flex-1 rounded border border-border bg-white"
              />
            ) : (
              <ArtifactRenderer artifact={artifact} projectId={projectId} />
            )}
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}

export function ArtifactMessage({ content }: Props) {
  const currentProjectId = useProjectStore((state) => state.currentProjectId)
  const artifacts = normalizeArtifacts(content)
  return (
    <div className="space-y-2">
      {artifacts.map((artifact, idx) => (
        <ArtifactCard
          key={`${artifact.path || artifact.name || 'artifact'}-${idx}`}
          artifact={artifact}
          projectId={currentProjectId}
        />
      ))}
    </div>
  )
}
