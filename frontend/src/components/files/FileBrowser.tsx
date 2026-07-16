import { useEffect, useState, useCallback } from 'react'
import { Folder, FileText, ChevronRight, ChevronLeft, Loader2, RefreshCw, Quote, Eye } from 'lucide-react'
import { fileApi, type FileEntry } from '@/services/api'
import { useProjectStore } from '@/stores/projectStore'
import { useChatStore } from '@/stores/chatStore'
import { Button, EmptyState } from '@/components/ui'
import { MarkdownRenderer } from '@/components/shared/MarkdownRenderer'
import { toastError, toastSuccess } from '@/stores/toastStore'
import { useTranslation } from '@/i18n'

interface BreadcrumbSegment {
  name: string
  path: string
}

const _MAX_READ_BYTES = 5 * 1024 * 1024

function isBinaryMimeType(mimeType: string): boolean {
  if (!mimeType) return false
  const binaryPrefixes = ['video/', 'audio/', 'application/pdf', 'application/zip']
  if (binaryPrefixes.some((prefix) => mimeType.startsWith(prefix))) return true
  // Application types other than known text formats are treated as binary.
  if (mimeType.startsWith('application/')) {
    const textSubtypes = ['json', 'yaml', 'x-yaml', 'javascript', 'xml', 'x-sh']
    return !textSubtypes.some((subtype) => mimeType.endsWith(subtype))
  }
  return false
}

function isImageFile(mimeType: string, name: string): boolean {
  if (mimeType && mimeType.startsWith('image/')) return true
  return /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(name)
}

function isSpreadsheetFile(mimeType: string, name: string): boolean {
  if (mimeType) {
    if (mimeType === 'text/csv' || mimeType === 'text/tab-separated-values') return true
  }
  return /\.(csv|tsv)$/i.test(name)
}

function isMarkdownFile(mimeType: string, name: string): boolean {
  if (mimeType && mimeType === 'text/markdown') return true
  return /\.(md|markdown|mdx)$/i.test(name)
}

function isJsonFile(mimeType: string, name: string): boolean {
  if (mimeType && (mimeType === 'application/json' || mimeType === 'text/json')) return true
  return /\.json$/i.test(name)
}

function prettyPrintJson(content: string): string {
  try {
    return JSON.stringify(JSON.parse(content), null, 2)
  } catch {
    return content
  }
}

function detectDelimiter(mimeType: string, name: string): string {
  if (mimeType === 'text/tab-separated-values' || /\.tsv$/i.test(name)) return '\t'
  return ','
}

/**
 * Lightweight CSV/TSV parser that respects double-quoted fields and escaped
 * quotes (""). Returns an empty array for empty content.
 */
function parseDelimited(content: string, delimiter: string): string[][] {
  if (!content) return []
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let inQuotes = false

  for (let i = 0; i < content.length; i++) {
    const char = content[i]
    const next = content[i + 1]

    if (inQuotes) {
      if (char === '"') {
        if (next === '"') {
          cell += '"'
          i++
        } else {
          inQuotes = false
        }
      } else {
        cell += char
      }
    } else {
      if (char === '"') {
        inQuotes = true
      } else if (char === delimiter) {
        row.push(cell)
        cell = ''
      } else if (char === '\r') {
        if (next === '\n') i++
        row.push(cell)
        rows.push(row)
        row = []
        cell = ''
      } else if (char === '\n') {
        row.push(cell)
        rows.push(row)
        row = []
        cell = ''
      } else {
        cell += char
      }
    }
  }

  if (cell || row.length > 0) {
    row.push(cell)
    rows.push(row)
  }

  // Drop a trailing empty row that often appears after a trailing newline.
  if (rows.length > 0 && rows[rows.length - 1].length === 1 && rows[rows.length - 1][0] === '') {
    rows.pop()
  }

  return rows
}

const _MAX_TABLE_ROWS = 500

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
    setFileMimeType('')
    // Default to the outputs directory so users immediately see analysis
    // results; they can still navigate up to the workspace root if needed.
    fetchEntries('outputs')
  }, [currentProjectId, fetchEntries])

  const handleEntryClick = async (entry: FileEntry) => {
    if (entry.type === 'directory') {
      setSelectedFile(null)
      setFileContent(null)
      setFileMimeType('')
      await fetchEntries(entry.path)
      return
    }
    setSelectedFile(entry)
    setReading(true)
    try {
      const res = await fileApi.readFile(currentProjectId, entry.path)
      const mime = res.data.mime_type
      setFileMimeType(mime)
      if (isImageFile(mime, entry.name)) {
        // Images are rendered from the authenticated file URL; no need to keep
        // the base64 payload in React state.
        setFileContent(null)
      } else if (res.data.encoding === 'base64') {
        setFileContent(`[Binary file: ${entry.name}]\nSize: ${res.data.size} bytes`)
      } else {
        setFileContent(res.data.content)
      }
    } catch (err: any) {
      toastError(err?.response?.data?.detail || t('files.readFailed'))
      setFileContent(null)
      setFileMimeType('')
    } finally {
      setReading(false)
    }
  }

  const navigateUp = () => {
    const parent = currentPath.split('/').slice(0, -1).join('/')
    fetchEntries(parent)
    setSelectedFile(null)
    setFileContent(null)
    setFileMimeType('')
  }

  const breadcrumbs: BreadcrumbSegment[] = [
    { name: t('files.root'), path: '' },
    ...currentPath.split('/').filter(Boolean).map((name, idx, parts) => ({
      name,
      path: parts.slice(0, idx + 1).join('/'),
    })),
  ]

  const renderPreview = () => {
    if (reading) {
      return (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      )
    }

    if (!selectedFile) return null

    // Image preview
    if (isImageFile(fileMimeType, selectedFile.name)) {
      return (
        <div className="flex items-start justify-center">
          <img
            src={fileApi.fileUrl(currentProjectId, selectedFile.path)}
            alt={selectedFile.name}
            className="max-h-full max-w-full rounded-lg border border-border object-contain shadow-sm"
          />
        </div>
      )
    }

    // Markdown preview
    if (fileContent !== null && isMarkdownFile(fileMimeType, selectedFile.name)) {
      return <MarkdownRenderer content={fileContent} />
    }

    // JSON pretty-print preview
    if (fileContent !== null && isJsonFile(fileMimeType, selectedFile.name)) {
      return (
        <pre className="whitespace-pre-wrap break-all font-mono text-xs leading-relaxed text-foreground">
          {prettyPrintJson(fileContent)}
        </pre>
      )
    }

    // CSV / TSV table preview
    if (fileContent !== null && isSpreadsheetFile(fileMimeType, selectedFile.name)) {
      const delimiter = detectDelimiter(fileMimeType, selectedFile.name)
      const rows = parseDelimited(fileContent, delimiter)
      if (rows.length === 0) {
        return (
          <pre className="whitespace-pre-wrap break-all font-mono text-xs leading-relaxed text-foreground">
            {fileContent}
          </pre>
        )
      }

      const headers = rows[0]
      const body = rows.slice(1)
      const displayed = body.slice(0, _MAX_TABLE_ROWS)
      const truncated = body.length > _MAX_TABLE_ROWS

      return (
        <div className="w-full overflow-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="sticky top-0 z-10 bg-muted">
              <tr>
                {headers.map((h, idx) => (
                  <th
                    key={idx}
                    className="border-b border-border px-3 py-2 font-semibold text-foreground"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {displayed.map((row, rIdx) => (
                <tr key={rIdx} className="hover:bg-muted/50">
                  {headers.map((_, cIdx) => (
                    <td
                      key={cIdx}
                      className="border-b border-border px-3 py-1.5 text-muted-foreground"
                    >
                      {row[cIdx] ?? ''}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {truncated && (
            <p className="mt-2 text-xs text-muted-foreground">
              {t('files.tableTruncated', { shown: _MAX_TABLE_ROWS, total: body.length })}
            </p>
          )}
        </div>
      )
    }

    // Fallback text / binary preview
    if (fileContent !== null) {
      return (
        <pre className="whitespace-pre-wrap break-all font-mono text-xs leading-relaxed text-foreground">
          {fileContent}
        </pre>
      )
    }

    return null
  }

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
                <div className="flex items-center gap-2">
                  {(selectedFile.size !== null && selectedFile.size > _MAX_READ_BYTES) ||
                  isBinaryMimeType(fileMimeType) ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        window.open(fileApi.previewUrl(currentProjectId, selectedFile.path), '_blank')
                      }}
                    >
                      <Eye className="mr-1.5 h-4 w-4" />
                      {t('domain.preview')}
                    </Button>
                  ) : null}
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
              </div>
              <div className="flex-1 overflow-auto p-4">{renderPreview()}</div>
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
