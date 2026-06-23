import { useState, useCallback, useEffect } from 'react'
import { clsx } from 'clsx'
import { Upload, Loader2, ImageIcon, Wand2, Play, BarChart3, BoxSelect, Activity, ToggleLeft, ToggleRight } from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import { useProjectStore } from '@/stores/projectStore'
import { useTranslation } from '@/i18n'
import { fileApi, vizApi } from '@/services/api'
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Select, Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui'
import { toastError, toastSuccess } from '@/stores/toastStore'
import { FigureGallery } from './FigureGallery'
import Plot from 'react-plotly.js'

const PLOT_TYPES = [
  { value: 'bar', label: 'Bar chart', icon: BarChart3 },
  { value: 'box', label: 'Box plot', icon: BoxSelect },
  { value: 'violin', label: 'Violin plot', icon: Activity },
]

const THEMES = [
  { value: 'nature', label: 'Nature' },
  { value: 'cell', label: 'Cell' },
  { value: 'science', label: 'Science' },
]

const TESTS = [
  { value: 't_test', label: 't-test' },
  { value: 'one_way_anova', label: 'ANOVA' },
]

const TABLE_TYPES = [
  { value: '', label: 'Auto detect' },
  { value: 'column', label: 'Column (groups in columns)' },
  { value: 'xy', label: 'XY (x vs y)' },
  { value: 'grouped', label: 'Grouped' },
  { value: 'survival', label: 'Survival' },
  { value: 'contingency', label: 'Contingency' },
]

function resolvePreviewUrl(projectId: string, result: { outputs?: Record<string, unknown>; artifacts?: Array<{ type: string; path: string; mime: string }> }): string | null {
  if (result.outputs?.preview_url && typeof result.outputs.preview_url === 'string') {
    return result.outputs.preview_url
  }
  const imageArtifact = result.artifacts?.find((a) => a.mime?.startsWith('image/'))
  if (imageArtifact?.path) {
    return `/api/files/${projectId}/${encodeURIComponent(imageArtifact.path)}`
  }
  const formats = result.outputs?.formats
  if (formats && typeof formats === 'object') {
    const firstPath = Object.values(formats as Record<string, string>)[0]
    if (firstPath) {
      return `/api/files/${projectId}/${encodeURIComponent(firstPath)}`
    }
  }
  return null
}

export function FigureWorkbench() {
  const { t } = useTranslation()
  const currentProjectId = useProjectStore((state) => state.currentProjectId)

  const [activeTab, setActiveTab] = useState('workbench')
  const [sourceFilename, setSourceFilename] = useState('')
  const [uploadedFilename, setUploadedFilename] = useState('')
  const [tableTypeHint, setTableTypeHint] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [sessionInfo, setSessionInfo] = useState<Record<string, unknown> | null>(null)
  const [dataId, setDataId] = useState('')
  const [plotType, setPlotType] = useState('box')
  const [theme, setTheme] = useState('nature')
  const [testName, setTestName] = useState('one_way_anova')
  const [editCommand, setEditCommand] = useState('')
  const [interpretation, setInterpretation] = useState('')
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [plotlyData, setPlotlyData] = useState<{ data: unknown[]; layout: Record<string, unknown> } | null>(null)
  const [figureId, setFigureId] = useState('')
  const [interactive, setInteractive] = useState(false)
  const [autoAnnotate, setAutoAnnotate] = useState(false)
  const [loading, setLoading] = useState<'upload' | 'session' | 'render' | 'edit' | null>(null)
  const [error, setError] = useState<string | null>(null)

  const resetSession = useCallback(() => {
    setSessionId('')
    setDataId('')
    setSessionInfo(null)
    setFigureId('')
    setPreviewUrl(null)
    setPlotlyData(null)
    setInterpretation('')
    setError(null)
  }, [])

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0]
      if (!file || !currentProjectId) return
      setError(null)
      setLoading('upload')
      try {
        const res = await fileApi.uploadFile(file, currentProjectId)
        const filename = res.data.filename || res.data.path.split('/').pop() || file.name
        setSourceFilename(filename)
        setUploadedFilename(filename)
        resetSession()
        toastSuccess(t('figures.uploadSuccess', { filename }))
      } catch (error: any) {
        const detail = error?.response?.data?.detail
        const message = detail || t('figures.uploadFailed', { filename: file.name })
        setError(message)
        toastError(message)
      } finally {
        setLoading(null)
      }
    },
    [currentProjectId, resetSession, t]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    noClick: false,
    multiple: false,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    },
  })

  const handleCreateSession = async () => {
    if (!currentProjectId || !sourceFilename) {
      toastError(t('figures.missingSource'))
      return
    }
    setError(null)
    setLoading('session')
    try {
      const res = await vizApi.createSession({
        project_id: currentProjectId,
        source_filename: sourceFilename,
        table_type_hint: tableTypeHint || null,
      })
      setSessionId(res.data.session_id)
      setDataId((res.data.outputs?.data_id as string) || '')
      setSessionInfo(res.data.outputs || null)
      setInterpretation(res.data.interpretation || '')
      toastSuccess(t('figures.sessionCreated'))
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      const message = detail || t('figures.sessionFailed')
      setError(message)
      toastError(message)
    } finally {
      setLoading(null)
    }
  }

  const handleRender = async () => {
    if (!currentProjectId || !sessionId) {
      toastError(t('figures.missingSession'))
      return
    }
    setError(null)
    setLoading('render')
    setPlotlyData(null)
    setPreviewUrl(null)
    try {
      const action = interactive ? 'render_plotly' : 'full_pipeline'
      const params: Record<string, unknown> = {
        source: sourceFilename,
        data_id: dataId,
        plot_type: plotType,
        theme,
        test_name: testName,
        auto_annotate: autoAnnotate,
      }
      if (!interactive) {
        params.formats = ['png', 'svg']
      }
      const res = await vizApi.render(sessionId, {
        project_id: currentProjectId,
        action,
        params,
      })
      if (!res.data.success) {
        const message = res.data.error || t('figures.renderFailed')
        setError(message)
        toastError(message)
        return
      }
      setFigureId((res.data.outputs?.figure_id as string) || '')
      setInterpretation(res.data.interpretation || '')

      if (interactive && res.data.outputs?.plotly_json) {
        const parsed = JSON.parse(res.data.outputs.plotly_json as string)
        setPlotlyData({ data: parsed.data, layout: parsed.layout })
      } else {
        const url = resolvePreviewUrl(currentProjectId, res.data)
        setPreviewUrl(url)
      }
      toastSuccess(t('figures.renderSuccess'))
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      const message = detail || t('figures.renderFailed')
      setError(message)
      toastError(message)
    } finally {
      setLoading(null)
    }
  }

  const handleVisionEdit = async () => {
    if (!currentProjectId || !sessionId || !figureId || !editCommand.trim()) {
      toastError(t('figures.missingEdit'))
      return
    }
    setError(null)
    setLoading('edit')
    try {
      const res = await vizApi.render(sessionId, {
        project_id: currentProjectId,
        action: 'vision_edit',
        params: {
          figure_id: figureId,
          commands: [editCommand.trim()],
        },
      })
      if (!res.data.success) {
        const message = res.data.error || t('figures.editFailed')
        setError(message)
        toastError(message)
        return
      }
      setFigureId((res.data.outputs?.figure_id as string) || figureId)
      setInterpretation(res.data.interpretation || '')
      const url = resolvePreviewUrl(currentProjectId, res.data)
      if (url) setPreviewUrl(url)
      setEditCommand('')
      toastSuccess(t('figures.editSuccess'))
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      const message = detail || t('figures.editFailed')
      setError(message)
      toastError(message)
    } finally {
      setLoading(null)
    }
  }

  useEffect(() => {
    if (!currentProjectId) {
      toastError(t('figures.noProject'))
    }
  }, [currentProjectId, t])

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 items-center justify-between border-b border-border bg-card px-4">
        <h2 className="text-base font-semibold">{t('figures.title')}</h2>
        <span className="text-xs text-muted-foreground">{t('figures.subtitle')}</span>
      </div>

      <Tabs defaultValue="workbench" value={activeTab} onValueChange={setActiveTab} className="flex-1 overflow-hidden">
        <div className="border-b border-border bg-card px-4 pt-3">
          <TabsList>
            <TabsTrigger value="workbench">{t('figures.tabWorkbench')}</TabsTrigger>
            <TabsTrigger value="gallery">{t('figures.tabGallery')}</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="workbench" className="h-[calc(100%-3rem)] overflow-auto p-4">
          <div className="grid h-full grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="space-y-4 lg:col-span-1">
              <Card>
                <CardHeader>
                  <CardTitle>{t('figures.dataPanelTitle')}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div
                    {...getRootProps()}
                    className={clsx(
                      'cursor-pointer rounded-lg border-2 border-dashed border-border p-4 text-center transition-colors hover:border-primary/50',
                      isDragActive && 'border-primary bg-primary/5'
                    )}
                  >
                    <input {...getInputProps()} />
                    <Upload className="mx-auto h-6 w-6 text-muted-foreground" />
                    <p className="mt-2 text-sm text-muted-foreground">{t('figures.dragOrClick')}</p>
                    <p className="text-xs text-muted-foreground">{t('figures.supportedFormats')}</p>
                  </div>

                  <Input
                    placeholder={t('figures.sourceFilenamePlaceholder')}
                    value={sourceFilename}
                    onChange={(e) => setSourceFilename(e.target.value)}
                  />

                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">{t('figures.tableType')}</label>
                    <Select value={tableTypeHint} onChange={(e) => setTableTypeHint(e.target.value)} options={TABLE_TYPES} />
                  </div>

                  <Button
                    onClick={handleCreateSession}
                    disabled={loading === 'session' || !sourceFilename || !currentProjectId}
                    loading={loading === 'session'}
                    className="w-full"
                  >
                    {loading === 'session' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                    {t('figures.createSession')}
                  </Button>

                  {uploadedFilename && (
                    <p className="text-xs text-muted-foreground">
                      {t('figures.uploadedFile', { filename: uploadedFilename })}
                    </p>
                  )}

                  {sessionInfo && (
                    <div className="rounded-md border border-border bg-muted p-3 text-xs">
                      <p className="font-medium">{t('figures.detectedStructure')}</p>
                      <p>{t('figures.detectedTableType', { type: sessionInfo.table_type as string })}</p>
                      {(sessionInfo.group_columns as string[])?.length > 0 && (
                        <p>
                          {t('figures.groupColumns')}: {(sessionInfo.group_columns as string[]).join(', ')}
                        </p>
                      )}
                      {(sessionInfo.quality_warnings as string[])?.length > 0 && (
                        <p className="mt-1 text-amber-600">
                          ⚠ {(sessionInfo.quality_warnings as string[]).join('; ')}
                        </p>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>{t('figures.configPanelTitle')}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">{t('figures.plotType')}</label>
                    <Select value={plotType} onChange={(e) => setPlotType(e.target.value)} options={PLOT_TYPES} />
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">{t('figures.theme')}</label>
                    <Select value={theme} onChange={(e) => setTheme(e.target.value)} options={THEMES} />
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">{t('figures.statTest')}</label>
                    <Select value={testName} onChange={(e) => setTestName(e.target.value)} options={TESTS} />
                  </div>

                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full justify-start px-2"
                    onClick={() => setInteractive((v) => !v)}
                  >
                    {interactive ? <ToggleRight className="h-4 w-4 text-primary" /> : <ToggleLeft className="h-4 w-4" />}
                    <span className="ml-2 text-xs">{t('figures.interactive')}</span>
                  </Button>

                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full justify-start px-2"
                    onClick={() => setAutoAnnotate((v) => !v)}
                  >
                    {autoAnnotate ? <ToggleRight className="h-4 w-4 text-primary" /> : <ToggleLeft className="h-4 w-4" />}
                    <span className="ml-2 text-xs">{t('figures.autoAnnotate')}</span>
                  </Button>

                  <Button
                    onClick={handleRender}
                    disabled={loading === 'render' || !sessionId}
                    loading={loading === 'render'}
                    className="w-full"
                  >
                    {t('figures.render')}
                  </Button>
                </CardContent>
              </Card>

              {figureId && (
                <Card>
                  <CardHeader>
                    <CardTitle>{t('figures.editPanelTitle')}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <Input
                      placeholder={t('figures.editPlaceholder')}
                      value={editCommand}
                      onChange={(e) => setEditCommand(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleVisionEdit()}
                    />
                    <Button
                      onClick={handleVisionEdit}
                      disabled={loading === 'edit' || !editCommand.trim()}
                      loading={loading === 'edit'}
                      variant="secondary"
                      className="w-full"
                    >
                      <Wand2 className="h-4 w-4" />
                      {t('figures.applyEdit')}
                    </Button>
                  </CardContent>
                </Card>
              )}
            </div>

            <div className="lg:col-span-2">
              <Card className="h-full">
                <CardHeader>
                  <CardTitle>{t('figures.previewTitle')}</CardTitle>
                </CardHeader>
                <CardContent className="flex h-[calc(100%-4rem)] flex-col items-center justify-center">
                  {plotlyData ? (
                    <Plot
                      data={plotlyData.data as Plotly.Data[]}
                      layout={{
                        ...plotlyData.layout,
                        autosize: true,
                      }}
                      style={{ width: '100%', height: '100%' }}
                      useResizeHandler
                    />
                  ) : previewUrl ? (
                    <img
                      src={previewUrl}
                      alt={t('figures.previewAlt')}
                      className="max-h-full max-w-full rounded-lg border border-border object-contain"
                    />
                  ) : (
                    <div className="text-center">
                      <ImageIcon className="mx-auto h-12 w-12 text-muted-foreground/50" />
                      <p className="mt-2 text-sm text-muted-foreground">{t('figures.previewEmpty')}</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>

          {interpretation && (
            <div className="mt-4 rounded-lg border border-border bg-muted p-3 text-sm text-foreground">
              {interpretation}
            </div>
          )}

          {error && (
            <div className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
        </TabsContent>

        <TabsContent value="gallery" className="h-[calc(100%-3rem)] overflow-auto p-4">
          <FigureGallery projectId={currentProjectId} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
