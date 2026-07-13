import { useEffect, useState } from 'react'
import { clsx } from 'clsx'
import { ImageIcon, RefreshCw, Download, Trash2, GitCompare } from 'lucide-react'
import { vizApi, fileApi } from '@/sdk'
import { useTranslation } from '@/i18n'
import { Button, Card, CardContent, CardHeader, CardTitle, EmptyState, Modal } from '@/components/ui'
import { toastError, toastSuccess } from '@/stores/toastStore'
import type { FigureItem } from '@/types/api'

interface FigureGalleryProps {
  projectId: string
}

export function FigureGallery({ projectId }: FigureGalleryProps) {
  const { t } = useTranslation()
  const [figures, setFigures] = useState<FigureItem[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [compareOpen, setCompareOpen] = useState(false)

  const loadFigures = async () => {
    if (!projectId) return
    setLoading(true)
    try {
      const res = await vizApi.listFigures(projectId)
      setFigures(res.data)
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      toastError(detail || t('figures.galleryLoadFailed'))
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = (path: string) => {
    const url = fileApi.fileUrl(projectId, path)
    window.open(url, '_blank')
  }

  const handleDelete = async (figureId: string) => {
    if (!window.confirm(t('figures.deleteConfirm'))) return
    try {
      await vizApi.deleteFigure(projectId, figureId)
      toastSuccess(t('figures.deleteSuccess'))
      setSelectedIds((prev) => {
        const next = new Set(prev)
        next.delete(figureId)
        return next
      })
      loadFigures()
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      toastError(detail || t('figures.deleteFailed'))
    }
  }

  const toggleSelect = (figureId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(figureId)) {
        next.delete(figureId)
      } else {
        next.add(figureId)
      }
      return next
    })
  }

  const selectedFigures = figures.filter((f) => selectedIds.has(f.figure_id))
  const canCompare = selectedFigures.length === 2

  useEffect(() => {
    loadFigures()
  }, [projectId])

  if (!projectId) {
    return (
      <EmptyState
        title={t('figures.noProject')}
        description={t('figures.selectProjectDesc')}
      />
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">{t('figures.galleryTitle')}</h3>
        <div className="flex items-center gap-2">
          {canCompare && (
            <Button variant="secondary" size="sm" onClick={() => setCompareOpen(true)}>
              <GitCompare className="mr-1 h-4 w-4" />
              {t('figures.compare')}
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={loadFigures} disabled={loading}>
            <RefreshCw className={clsx('h-4 w-4', loading && 'animate-spin')} />
            {t('common.refresh')}
          </Button>
        </div>
      </div>

      {figures.length === 0 ? (
        <EmptyState
          title={t('figures.empty')}
          description={t('figures.emptyDesc')}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {figures.map((figure) => (
            <Card key={figure.figure_id} className="overflow-hidden">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm">{figure.figure_id}</CardTitle>
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border"
                  checked={selectedIds.has(figure.figure_id)}
                  onChange={() => toggleSelect(figure.figure_id)}
                  aria-label={t('figures.selectForCompare')}
                />
              </CardHeader>
              <CardContent className="space-y-2">
                {figure.preview_url ? (
                  <img
                    src={figure.preview_url}
                    alt={figure.figure_id}
                    className="aspect-video w-full rounded-lg border border-border object-contain"
                  />
                ) : (
                  <div className="flex aspect-video w-full items-center justify-center rounded-lg border border-border bg-muted">
                    <ImageIcon className="h-8 w-8 text-muted-foreground/50" />
                  </div>
                )}
                <div className="flex flex-wrap gap-1">
                  {Object.keys(figure.formats).map((fmt) => (
                    <span key={fmt} className="rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase text-muted-foreground">
                      {fmt}
                    </span>
                  ))}
                </div>
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs text-muted-foreground">
                    {new Date(figure.created_at).toLocaleString()}
                  </p>
                  <div className="flex items-center gap-1">
                    {Object.entries(figure.formats).map(([fmt, path]) => (
                      <Button
                        key={fmt}
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        title={`${t('figures.download')} ${fmt.toUpperCase()}`}
                        onClick={() => handleDownload(path as string)}
                      >
                        <Download className="h-3.5 w-3.5" />
                      </Button>
                    ))}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive hover:text-destructive"
                      title={t('figures.delete')}
                      onClick={() => handleDelete(figure.figure_id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={compareOpen}
        onClose={() => setCompareOpen(false)}
        title={t('figures.compareTitle')}
        size="full"
      >
        {selectedFigures.length === 2 ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {selectedFigures.map((figure) => (
              <div key={figure.figure_id} className="space-y-2">
                <p className="text-sm font-medium">{figure.figure_id}</p>
                {figure.preview_url ? (
                  <img
                    src={figure.preview_url}
                    alt={figure.figure_id}
                    className="w-full rounded-lg border border-border object-contain"
                  />
                ) : (
                  <div className="flex aspect-video w-full items-center justify-center rounded-lg border border-border bg-muted">
                    <ImageIcon className="h-8 w-8 text-muted-foreground/50" />
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">{t('figures.selectTwo')}</p>
        )}
      </Modal>
    </div>
  )
}
