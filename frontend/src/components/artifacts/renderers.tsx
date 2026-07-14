import { useEffect, useState } from 'react'
import { Download, FileText } from 'lucide-react'
import { fileApi } from '@/sdk'
import type { Artifact } from './types'
import type { ArtifactRendererProps } from './registry'

export function artifactUrl(projectId: string | undefined, artifact: Artifact): string | null {
  if (artifact.url) return artifact.url
  if (artifact.preview_url) return artifact.preview_url
  if (artifact.path && projectId) {
    const marker = `/workspaces/${projectId}/`
    const idx = artifact.path.indexOf(marker)
    const rel =
      idx >= 0
        ? artifact.path.slice(idx + marker.length)
        : artifact.path.replace(/^.*\/(outputs|results|data)\//, '$1/')
    return fileApi.fileUrl(projectId, rel)
  }
  return null
}

export function downloadName(artifact: Artifact): string {
  return artifact.name || artifact.path?.split('/').pop() || 'download'
}

export function ImageArtifact({ artifact, projectId }: ArtifactRendererProps) {
  const url = artifactUrl(projectId, artifact)
  if (!url) return <FileArtifact artifact={artifact} projectId={projectId} />
  return (
    <img
      src={url}
      alt={downloadName(artifact)}
      className="max-h-96 w-full rounded border border-border bg-white object-contain"
    />
  )
}

interface ParsedTable {
  header: string[]
  rows: string[][]
  truncated: boolean
}

function parseDelimited(text: string, delimiter: string, maxRows: number): ParsedTable {
  const lines = text.split(/\r?\n/).filter((l) => l.length > 0)
  const [head, ...rest] = lines
  const header = (head || '').split(delimiter)
  const rows = rest.slice(0, maxRows).map((l) => l.split(delimiter))
  return { header, rows, truncated: rest.length > maxRows }
}

export function TableArtifact({ artifact, projectId }: ArtifactRendererProps) {
  const url = artifactUrl(projectId, artifact)
  const [state, setState] = useState<{ loading: boolean; table?: ParsedTable; error?: string }>({
    loading: true,
  })

  useEffect(() => {
    if (!url) {
      setState({ loading: false, error: 'No preview URL' })
      return
    }
    let cancelled = false
    const delimiter = artifact.name?.toLowerCase().endsWith('.tsv') ? '\t' : ','
    fetch(url)
      .then((res) => (res.ok ? res.text() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then((text) => {
        if (!cancelled) setState({ loading: false, table: parseDelimited(text, delimiter, 50) })
      })
      .catch((err) => {
        if (!cancelled) setState({ loading: false, error: String(err) })
      })
    return () => {
      cancelled = true
    }
  }, [url, artifact.name])

  if (state.loading) return <p className="text-xs text-slate-500">加载表格预览…</p>
  if (state.error || !state.table) return <FileArtifact artifact={artifact} projectId={projectId} />
  const { header, rows, truncated } = state.table
  return (
    <div className="max-h-96 overflow-auto rounded border border-border">
      <table className="w-full border-collapse text-xs">
        <thead className="sticky top-0 bg-muted">
          <tr>
            {header.map((h, i) => (
              <th key={i} className="border-b border-border px-2 py-1 text-left font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
            <tr key={r} className="odd:bg-muted/30">
              {row.map((cell, c) => (
                <td key={c} className="border-b border-border/50 px-2 py-0.5">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {truncated && <p className="px-2 py-1 text-[10px] text-slate-400">仅显示前 50 行</p>}
    </div>
  )
}

export function HtmlArtifact({ artifact, projectId }: ArtifactRendererProps) {
  const url = artifactUrl(projectId, artifact)
  if (!url) return <FileArtifact artifact={artifact} projectId={projectId} />
  return <iframe src={url} title={downloadName(artifact)} sandbox="" className="h-96 w-full rounded border border-border bg-white" />
}

export function PdfArtifact({ artifact, projectId }: ArtifactRendererProps) {
  const url = artifactUrl(projectId, artifact)
  if (!url) return <FileArtifact artifact={artifact} projectId={projectId} />
  return <iframe src={url} title={downloadName(artifact)} className="h-[32rem] w-full rounded border border-border bg-white" />
}

export function JsonArtifact({ artifact, projectId }: ArtifactRendererProps) {
  const [text, setText] = useState<string | null>(artifact.data ? JSON.stringify(artifact.data, null, 2) : null)
  const url = artifactUrl(projectId, artifact)

  useEffect(() => {
    if (text !== null || !url) return
    let cancelled = false
    fetch(url)
      .then((res) => (res.ok ? res.text() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then((raw) => {
        if (cancelled) return
        try {
          setText(JSON.stringify(JSON.parse(raw), null, 2))
        } catch {
          setText(raw)
        }
      })
      .catch(() => {
        if (!cancelled) setText(null)
      })
    return () => {
      cancelled = true
    }
  }, [url, text])

  if (text === null) return <FileArtifact artifact={artifact} projectId={projectId} />
  return (
    <pre className="max-h-96 overflow-auto rounded border border-border bg-muted/30 p-3 text-[11px] leading-relaxed">
      <code>{text}</code>
    </pre>
  )
}

export function AnndataArtifact({ artifact, projectId }: ArtifactRendererProps) {
  const url = artifactUrl(projectId, artifact)
  return (
    <div className="flex items-center gap-2 rounded border border-border bg-muted/30 px-3 py-2 text-xs">
      <FileText className="h-4 w-4 text-primary" />
      <span className="flex-1 truncate" title={downloadName(artifact)}>
        AnnData：{downloadName(artifact)}
      </span>
      {url && (
        <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">
          <Download className="h-3.5 w-3.5" /> 下载
        </a>
      )}
    </div>
  )
}

export function FileArtifact({ artifact, projectId }: ArtifactRendererProps) {
  const url = artifactUrl(projectId, artifact)
  return (
    <div className="flex items-center gap-2 rounded border border-border bg-muted/30 px-3 py-2 text-xs">
      <FileText className="h-4 w-4 text-slate-400" />
      <span className="flex-1 truncate" title={downloadName(artifact)}>
        {downloadName(artifact)}
      </span>
      {url && (
        <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">
          <Download className="h-3.5 w-3.5" /> 下载
        </a>
      )}
    </div>
  )
}
