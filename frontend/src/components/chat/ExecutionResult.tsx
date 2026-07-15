import { Download, FileText, Workflow } from 'lucide-react'
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
  const isSuccess = normalizedResult?.success === true
  const isFailure = normalizedResult?.success === false || normalizedResult?.status === 'failure'
  const failureMessage =
    normalizedResult?.error || normalizedResult?.error_message || normalizedResult?.detail

  const summaryText =
    normalizedResult?.final_output?.summary || normalizedResult?.summary || content.text

  const messageArtifacts: Artifact[] = Array.isArray(normalizedResult?.artifacts)
    ? (normalizedResult!.artifacts as Artifact[])
    : Array.isArray(content.artifacts)
    ? content.artifacts
    : []

  return (
    <div className="space-y-3 text-[15px] leading-relaxed">
      {summaryText && <MarkdownRenderer content={summaryText} />}

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

      {isSuccess && messageArtifacts.length > 0 && renderArtifactLinks(messageArtifacts, content.project_id, t)}

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

function renderArtifactLinks(items: Artifact[], projectId: string | undefined, t: (key: string) => string) {
  return (
    <div className="mt-2 space-y-1">
      <p className="text-xs font-medium text-foreground/80">
        {t('common.output')} ({items.length})
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
