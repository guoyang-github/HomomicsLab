import { FigureWorkbench } from '@/components/Figures'
import { PlotChart } from '@/components/shared/PlotChart'
import type { PlotContent, PlotDataContent } from '@/types/chat'

interface FigureOverlayProps {
  params?: Record<string, unknown>
}

export function FigureOverlay({ params }: FigureOverlayProps) {
  const plot = params?.plot as
    | { type: 'plot'; content: PlotContent }
    | { type: 'plot_data'; content: PlotDataContent }
    | undefined

  if (plot?.type === 'plot') {
    const content = plot.content
    return (
      <div className="flex h-full items-center justify-center p-4 sm:p-8">
        <img
          src={`data:image/png;base64,${content.image_base64}`}
          alt={content.plot_type}
          className="max-h-full max-w-full rounded-lg border border-border object-contain shadow-card"
        />
      </div>
    )
  }

  if (plot?.type === 'plot_data') {
    const content = plot.content
    return (
      <div className="flex h-full flex-col p-4 sm:p-8">
        <PlotChart
          request={{
            plot_type: content.plot_type as any,
            data: content.data,
            title: content.title,
            width: 1200,
            height: 800,
          }}
          className="h-full w-full rounded-lg border border-border"
        />
      </div>
    )
  }

  return <FigureWorkbench />
}
