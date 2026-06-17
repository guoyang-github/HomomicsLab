import { useEffect, useState, useCallback } from 'react'
import { Folder, FileText, ChevronRight, ChevronLeft, Loader2, RefreshCw, Quote } from 'lucide-react'
import { fileApi, type FileEntry } from '@/services/api'
import { useProjectStore } from '@/stores/projectStore'
import { useChatStore } from '@/stores/chatStore'
import { Button, EmptyState } from '@/components/ui'
import { toastError, toastSuccess } from '@/stores/toastStore'
import { useTranslation } from '@/i18n'

interface BreadcrumbSegment {
  name: string
  path: string
}

export function FileBrowser() {
  const { t } = useTranslation()
  const currentProjectId = useProjectStore((state) => state.currentProjectId)
  const [currentPath, setCurrentPath] = useState('')
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedFile, setSelectedFile] = useState<FileEntry | null>(null)
  const [fileContent, setFileContent] = useState<string | null>(null)
  const [fileMimeType, setFileMimeType] = useState<string>('')
  const [reading, setReading] = useState(false)

  const fetchEntries = useCallback(
    async (path: string) => {
      setLoading(true)
      try {
        const res = await fileApi.listFiles(currentProjectId, path)
        setEntries(res.data.entries)
        setCurrentPath(res.data.path)
      } catch (err: any) {
        toastError(err?.response?.data?.detail || t('files.loadFailed'))
      } finally {
        setLoading(false)
      }
    },
    [currentProjectId, t]
  )

  useEffect(() => {
    setSelectedFile(null)
    setFileContent(null)
    fetchEntries('')
  }, [currentProjectId, fetchEntries])

  const handleEntryClick = async (entry: FileEntry) => {
    if (entry.type === 'directory') {
      setSelectedFile(null)
      setFileContent(null)
      await fetchEntries(entry.path)
      return
    }
    setSelectedFile(entry)
    setReading(true)
    try {
      const res = await fileApi.readFile(currentProjectId, entry.path)
      setFileMimeType(res.data.mime_type)
      if (res.data.encoding === 'base64') {
        setFileContent(`[Binary file: ${entry.name}]\nSize: ${res.data.size} bytes`)
      } else {
        setFileContent(res.data.content)
      }
    } catch (err: any) {
      toastError(err?.response?.data?.detail || t('files.readFailed'))
      setFileContent(null)
    } finally {
      setReading(false)
    }
  }

  const navigateUp = () => {
    const parent = currentPath.split('/').slice(0, -1).join('/')
    fetchEntries(parent)
    setSelectedFile(null)
    setFileContent(null)
  }

  const breadcrumbs: BreadcrumbSegment[] = [
    { name: t('files.root'), path: '' },
    ...currentPath.split('/').filter(Boolean).map((name, idx, parts) => ({
      name,
      path: parts.slice(0, idx + 1).join('/'),
    })),
  ]

  return (
    <div className="flex h-full flex-col overflow-hidden bg-background p-4">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">{t('files.title')}</h2>
          <p className="text-sm text-muted-foreground">{t('files.subtitle')}</p>
        </div>
        <Button size="sm" variant="outline" onClick={() => fetchEntries(currentPath)} disabled={loading}>
          <RefreshCw className={cn('mr-1.5 h-4 w-4', loading && 'animate-spin')} />
          {t('common.refresh')}
        </Button>
      </div>

      <div className="flex min-h-0 flex-1 gap-4">
        <div className="flex w-80 flex-col overflow-hidden rounded-xl border border-border bg-card">
          <div className="flex items-center gap-2 border-b border-border p-3">
            <Button
              size="sm"
              variant="ghost"
              onClick={navigateUp}
              disabled={!currentPath}
              className="h-8 w-8 p-0"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <div className="flex flex-1 flex-wrap items-center gap-1 text-xs text-muted-foreground">
              {breadcrumbs.map((crumb, idx) => (
                <span key={crumb.path} className="flex items-center">
                  {idx > 0 && <ChevronRight className="mx-0.5 h-3 w-3" />}
                  <button
                    onClick={() => fetchEntries(crumb.path)}
                    className="hover:text-foreground"
                  >
                    {crumb.name}
                  </button>
                </span>
              ))}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-2">
            {loading && entries.length === 0 ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : entries.length === 0 ? (
              <EmptyState
                icon={Folder}
                title={t('files.empty')}
                description={t('files.emptyDesc')}
              />
            ) : (
              <ul className="space-y-1">
                {entries.map((entry) => (
                  <li key={entry.path}>
                    <button
                      onClick={() => handleEntryClick(entry)}
                      className={cn(
                        'flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm transition-colors',
                        selectedFile?.path === entry.path
                          ? 'bg-primary/10 text-primary'
                          : 'text-foreground hover:bg-muted'
                      )}
                    >
                      {entry.type === 'directory' ? (
                        <Folder className="h-4 w-4 shrink-0 text-amber-500" />
                      ) : (
                        <FileText className="h-4 w-4 shrink-0 text-blue-500" />
                      )}
                      <span className="flex-1 truncate">{entry.name}</span>
                      {entry.size !== null && (
                        <span className="text-xs text-muted-foreground">{formatSize(entry.size)}</span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="flex flex-1 flex-col overflow-hidden rounded-xl border border-border bg-card">
          {selectedFile ? (
            <>
              <div className="flex items-center justify-between border-b border-border px-4 py-3">
                <div>
                  <h3 className="font-medium text-foreground">{selectedFile.name}</h3>
                  <p className="text-xs text-muted-foreground">
                    {fileMimeType || selectedFile.type} · {formatSize(selectedFile.size || 0)}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    useChatStore.getState().setDraftInput(`@file:${selectedFile.path}`)
                    toastSuccess(t('files.referenceSuccess'))
                  }}
                >
                  <Quote className="mr-1.5 h-4 w-4" />
                  {t('files.reference')}
                </Button>
              </div>
              <div className="flex-1 overflow-auto p-4">
                {reading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                ) : fileContent !== null ? (
                  <pre className="whitespace-pre-wrap break-all font-mono text-xs leading-relaxed text-foreground">
                    {fileContent}
                  </pre>
                ) : null}
              </div>
            </>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center p-8 text-center text-muted-foreground">
              <FileText className="mb-3 h-12 w-12 opacity-20" />
              <p>{t('files.selectHint')}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(' ')
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`
}
