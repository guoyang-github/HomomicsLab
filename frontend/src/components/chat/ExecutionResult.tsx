import { clsx } from 'clsx'
import { Download, FileText, Workflow, CheckCircle2, Circle } from 'lucide-react'
import { useExecutionStore } from '@/stores/executionStore'
import { useOverlayStore } from '@/stores/overlayStore'
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
  for (const key of ['output_files', 'output_paths', 'output_csv', 'output_h5ad']) {
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

interface DisplaySubtask {
  id: string
  description: string
  analysis_type?: string
}

function collectSubtasks(tasks: TaskNode[] | undefined): { id: string; description: string; status: TaskNode['status'] }[] {
  if (!tasks) return []
  const items: { id: string; description: string; status: TaskNode['status'] }[] = []
  for (const task of tasks) {
    const raw = task.parameters?.display_subtasks
    if (Array.isArray(raw) && raw.length >= 2) {
      for (const sub of raw) {
        if (typeof sub === 'object' && sub !== null && typeof (sub as DisplaySubtask).description === 'string') {
          items.push({
            id: (sub as DisplaySubtask).id || `${task.id}_sub_${items.length}`,
            description: (sub as DisplaySubtask).description,
            status: task.status,
          })
        }
      }
    }
  }
  return items
}

function isRichSummary(text: string): boolean {
  // Rich summaries produced by the backend result_summary module contain
  // section headers, tables, or sourced findings. Generic fallbacks like
  // "分析已完成" are not rich.
  if (!text || text.length < 30) return false
  const hasSection = /\*\*(关键指标|关键发现|解读|下一步建议|CellTypist|注释结果|一致性比较|结果|来源)\*\*/.test(text)
  const hasTable = /\n\|[^\n]+\|\n\|[-:| ]+\|/.test(text)
  const hasFinding = /^\d+\.\s+/m.test(text)
  return hasSection || hasTable || hasFinding
}

export function ExecutionResult({ content }: Props) {
  const { t } = useTranslation()
  const executionStatus = useExecutionStore((state) => state.status)
  const executionResult = useExecutionStore((state) => state.result)
  const openWorkflow = useOverlayStore((state) => state.openWorkflow)

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

  // Prefer the deterministic rich summary the backend embeds in the TODO card.
  // Only fall back to the skill's own summary when the backend did not produce
  // a rich one, so the chat always shows sourced tables/metrics when available.
  const summaryText = isRichSummary(content.text)
    ? content.text
    : normalizedResult?.final_output?.summary || normalizedResult?.summary || content.text

  const messageArtifacts: Artifact[] = Array.isArray(normalizedResult?.artifacts)
    ? (normalizedResult!.artifacts as Artifact[])
    : Array.isArray(content.artifacts)
    ? content.artifacts
    : []

  const outputFiles = collectOutputFiles(normalizedResult)
  const subtaskItems = collectSubtasks(content.tasks)

  return (
    <div className="space-y-3 text-[15px] leading-relaxed">
      {summaryText && <MarkdownRenderer content={summaryText} />}

      {subtaskItems.length > 0 && (
        <div className="space-y-1.5 rounded-lg border border-border-faint bg-surface/50 p-3">
          {subtaskItems.map((item) => (
            <div key={item.id} className="flex items-center gap-2 text-sm">
              {item.status === 'completed' ? (
                <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
              ) : item.status === 'failed' ? (
                <FileText className="h-4 w-4 shrink-0 text-error" />
              ) : (
                <Circle className="h-4 w-4 shrink-0 text-muted-foreground" />
              )}
              <span
                className={clsx(
                  'flex-1',
                  item.status === 'completed' && 'text-muted-foreground line-through',
                  item.status === 'failed' && 'text-error'
                )}
              >
                {item.description}
              </span>
            </div>
          ))}
        </div>
      )}

      {content.tasks?.length > 0 && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => openWorkflow()}
            className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-accent transition-colors hover:bg-accent/10"
          >
            <Workflow className="h-3.5 w-3.5" />
            {t('todoList.viewWorkflow')}
          </button>
        </div>
      )}

      {executionStatus === 'running' && content.job_id && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-success" />
          <span>{t('executionLog.running')}</span>
        </div>
      )}

      {messageArtifacts.length > 0 && renderArtifactLinks(messageArtifacts, content.project_id, t, isFailure)}

      {outputFiles.length > 0 && messageArtifacts.length === 0 &&
        renderFileLinks(outputFiles, content.project_id, t)}

      {isFailure && (
        <div className="rounded-lg border border-error/30 bg-error/5 p-3">
          <div className="mb-1 text-sm font-medium text-error">{t('executionLog.failed')}</div>
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
  failed?: boolean
) {
  return (
    <div className="mt-2 space-y-1">
      <p className="text-xs font-medium text-foreground/80">
        {failed ? t('common.output') : t('common.output')} ({items.length})
      </p>
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

function renderFileLinks(paths: string[], projectId: string | undefined, t: (key: string) => string) {
  return (
    <div className="mt-2 space-y-1">
      <p className="text-xs font-medium text-foreground/80">
        {t('common.output')} ({paths.length})
      </p>
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
