import { Download, FileText, XCircle } from 'lucide-react'
import { useExecutionStore } from '@/stores/executionStore'
import { useTranslation } from '@/i18n'
import { MarkdownRenderer } from '@/components/shared/MarkdownRenderer'
import { fileApi } from '@/sdk'
import type { Artifact } from '@/components/artifacts'
import type { TaskNode } from '@/types/tasks'

interface Props {
  content: {
    text: string
    tasks: TaskNode[]
    job_id?: string
    project_id?: string
    result?: Record<string, any>
    status?: string
    artifacts?: Artifact[]
  }
  mode?: 'full' | 'outputs-only'
}

function normalizeResult(raw: Record<string, any> | null | undefined): Record<string, any> | null {
  if (!raw) return null
  if (raw.success !== undefined || raw.status === 'failure') {
    return raw
  }
  if (raw.result && typeof raw.result === 'object') {
    return raw.result as Record<string, any>
  }
  return raw
}

function collectOutputFiles(normalized: Record<string, any> | null): string[] {
  if (!normalized) return []
  const out: string[] = []
  for (const key of ['output_files', 'output_paths', 'output_csv', 'output_h5ad', 'output_summary', 'comparison_csv']) {
    const val = normalized[key]
    if (typeof val === 'string' && val) {
      out.push(val)
    } else if (Array.isArray(val)) {
      val.forEach((v) => typeof v === 'string' && v && out.push(v))
    }
  }
  return [...new Set(out)]
}

function fileLink(projectId: string | undefined, path: string): string | null {
  if (!projectId || !path) return null
  const marker = `/workspaces/${projectId}/`
  const idx = path.indexOf(marker)
  const rel =
    idx >= 0
      ? path.slice(idx + marker.length)
      : path.replace(/^.*\/(outputs|results|data)\//, '$1/')
  return fileApi.fileUrl(projectId, rel)
}

function artifactLink(projectId: string | undefined, artifact: Artifact): string | null {
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

function formatSize(bytes: unknown): string {
  const n = typeof bytes === 'number' ? bytes : Number(bytes)
  if (!Number.isFinite(n) || n <= 0) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${(n / 1024 / 1024 / 1024).toFixed(1)} GB`
}

function isRichSummary(text: string): boolean {
  if (!text || text.length < 30) return false
  const hasSection = /\*\*(关键指标|关键发现|解读|下一步建议|CellTypist|注释结果|一致性比较|结果|来源)\*\*/.test(text)
  const hasTable = /\n\|[^\n]+\|\n\|[-:| ]+\|/.test(text)
  const hasFinding = /^\d+\.\s+/m.test(text)
  return hasSection || hasTable || hasFinding
}

function isGenericPlaceholder(text: string): boolean {
  if (!text) return true
  const lowered = text.trim().toLowerCase()
  return (
    lowered === '分析已完成。' ||
    lowered === '分析已完成' ||
    lowered.startsWith('执行结束') ||
    lowered.startsWith('抱歉，处理您的请求时出现了问题')
  )
}

function formatObjectSummary(obj: Record<string, any>): string {
  const lines: string[] = []
  const scalarKeys = Object.keys(obj).filter((k) => {
    const v = obj[k]
    if (v === null || v === undefined) return false
    if (typeof v === 'string' && v.startsWith('/')) return false
    if (Array.isArray(v)) return false
    if (typeof v === 'object') return false
    return true
  })
  if (scalarKeys.length > 0) {
    lines.push('**关键指标**')
    scalarKeys.forEach((k) => {
      const value = obj[k]
      lines.push(`- ${k}：${typeof value === 'number' ? (Number.isInteger(value) ? value : value.toFixed(3)) : value}`)
    })
  }
  return lines.join('\n')
}

export function ExecutionResult({ content, mode = 'full' }: Props) {
  const { t } = useTranslation()
  const executionResult = useExecutionStore((state) => state.result)

  const taskResult =
    content.tasks?.find(
      (task) =>
        (task.status === 'completed' || task.status === 'failed') &&
        task.result &&
        typeof task.result === 'object'
    )?.result || null
  const rawResult = content.result || taskResult || executionResult
  const normalizedResult = normalizeResult(rawResult)
  const isFailure =
    normalizedResult?.success === false ||
    normalizedResult?.status === 'failure' ||
    content.status === 'failed'
  const failureMessage =
    normalizedResult?.error || normalizedResult?.error_message || normalizedResult?.detail

  const outputsOnly = mode === 'outputs-only'

  // Prefer deterministic rich summaries; otherwise use any explicit summary/text
  // the skill returned. If the backend placeholder is generic and we have a result,
  // fall back to a structured key-value rendering instead of "分析已完成。"
  // Informative status text (e.g. "已提交后台执行...") is still shown in
  // outputs-only mode so the card is never empty; only the raw task-checklist
  // placeholder is skipped because the floating TODO panel already shows status.
  let summaryText = ''
  if (isRichSummary(content.text)) {
    summaryText = content.text
  } else {
    const explicitSummary =
      normalizedResult?.final_output?.summary ||
      normalizedResult?.summary ||
      normalizedResult?.text ||
      content.text
    if (explicitSummary && typeof explicitSummary === 'string' && !isGenericPlaceholder(explicitSummary)) {
      summaryText = explicitSummary
    } else if (!outputsOnly && normalizedResult && !isFailure) {
      summaryText = formatObjectSummary(normalizedResult)
    }
  }

  const messageArtifacts: Artifact[] = Array.isArray(normalizedResult?.artifacts)
    ? (normalizedResult!.artifacts as Artifact[])
    : Array.isArray(content.artifacts)
    ? content.artifacts
    : []

  const outputFiles = collectOutputFiles(normalizedResult)

  return (
    <div className="space-y-3 text-[15px] leading-relaxed">
      {summaryText ? <MarkdownRenderer content={summaryText} /> : null}

      {messageArtifacts.length > 0 &&
        renderArtifactLinks(messageArtifacts, content.project_id, t, !outputsOnly)}

      {outputFiles.length > 0 && messageArtifacts.length === 0 &&
        renderFileLinks(outputFiles, content.project_id, t, !outputsOnly)}

      {isFailure && (
        <div className="rounded-lg border border-error/30 bg-error/5 p-3">
          <div className="mb-1 flex items-center gap-2 text-sm font-medium text-error">
            <XCircle className="h-4 w-4" />
            {t('executionLog.failed')}
          </div>
          <p className="text-xs text-foreground/80">
            {failureMessage || '请查看执行日志了解详情。'}
          </p>
        </div>
      )}
    </div>
  )
}

function renderArtifactLinks(
  items: Artifact[],
  projectId: string | undefined,
  t: (key: string) => string,
  showHeader = true
) {
  return (
    <div className="space-y-1">
      {showHeader && (
        <p className="text-xs font-medium text-foreground/80">
          {t('common.output')} ({items.length})
        </p>
      )}
      {items.map((artifact, idx) => {
        const href = artifactLink(projectId, artifact)
        const name = artifact.name || artifact.path?.split('/').pop() || `file-${idx}`
        const size = formatSize(artifact.size)
        return (
          <div
            key={`${artifact.path || name}-${idx}`}
            className="flex items-center gap-2 rounded border border-border-faint bg-surface px-3 py-1.5 text-xs"
          >
            <FileText className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
            <span className="flex-1 truncate" title={name}>
              {name}
            </span>
            {size && <span className="text-[10px] text-muted-foreground">{size}</span>}
            {href && (
              <a
                href={href}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-accent hover:underline"
              >
                <Download className="h-3.5 w-3.5" /> {t('common.download')}
              </a>
            )}
          </div>
        )
      })}
    </div>
  )
}

function renderFileLinks(paths: string[], projectId: string | undefined, t: (key: string) => string, showHeader = true) {
  return (
    <div className="space-y-1">
      {showHeader && (
        <p className="text-xs font-medium text-foreground/80">
          {t('common.output')} ({paths.length})
        </p>
      )}
      {paths.map((path, idx) => {
        const href = fileLink(projectId, path)
        const name = path.split('/').pop() || `file-${idx}`
        return (
          <div
            key={`${path}-${idx}`}
            className="flex items-center gap-2 rounded border border-border-faint bg-surface px-3 py-1.5 text-xs"
          >
            <FileText className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
            <span className="flex-1 truncate" title={name}>
              {name}
            </span>
            {href && (
              <a
                href={href}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-accent hover:underline"
              >
                <Download className="h-3.5 w-3.5" /> {t('common.download')}
              </a>
            )}
          </div>
        )
      })}
    </div>
  )
}
