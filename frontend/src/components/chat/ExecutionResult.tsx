import { useState } from 'react'
import { Download, FileText, Square, Workflow } from 'lucide-react'
import { useExecutionStore } from '@/stores/executionStore'
import { useOverlayStore } from '@/stores/overlayStore'
import { useTranslation } from '@/i18n'
import { MarkdownRenderer } from '@/components/shared/MarkdownRenderer'
import { fileApi, executionApi } from '@/sdk'
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

function isRichSummary(text: string): boolean {
  return typeof text === 'string' && /\*\*(关键指标|关键发现|解读|CellTypist|注释结果|一致性比较|结果)\*\*/.test(text)
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

function fileLink(projectId: string | undefined, path: string): string | null {
  if (!projectId || !path) return null
  const marker = `/workspaces/${projectId}/`
  const idx = path.indexOf(marker)
  const rel = idx >= 0 ? path.slice(idx + marker.length) : path.replace(/^.*\/(outputs|results|data)\//, '$1/')
  return `/files/${projectId}/${rel}`
}

export function ExecutionResult({ content }: Props) {
  const { t } = useTranslation()
  const executionStatus = useExecutionStore((state) => state.status)
  const executionResult = useExecutionStore((state) => state.result)
  const openWorkflow = useOverlayStore((state) => state.openWorkflow)

  const isRunning = executionStatus === 'running' && content.job_id

  const taskResult =
    content.tasks?.find(
      (t) =>
        (t.status === 'completed' || t.status === 'failed') &&
        t.result &&
        typeof t.result === 'object'
    )?.result || null
  const rawResult = content.result || taskResult || executionResult
  const normalizedResult = normalizeResult(rawResult)
  const isSuccess = normalizedResult?.success === true
  const isFailure = normalizedResult?.success === false || normalizedResult?.status === 'failure'
  const failureMessage =
    normalizedResult?.error || normalizedResult?.error_message || normalizedResult?.detail

  const [cancelling, setCancelling] = useState(false)
  const handleCancel = async () => {
    if (!content.job_id || !isRunning) return
    setCancelling(true)
    try {
      await executionApi.cancel(content.job_id)
    } catch {
      // ignore
    }
  }

  const rich = isRichSummary(content.text)
  const summaryText =
    normalizedResult?.final_output?.summary ||
    normalizedResult?.summary ||
    (rich ? content.text : '')
  const showPlaceholder = !summaryText && content.text

  const messageArtifacts: Artifact[] = Array.isArray(normalizedResult?.artifacts)
    ? (normalizedResult!.artifacts as Artifact[])
    : Array.isArray(content.artifacts)
    ? content.artifacts
    : []

  const outputFiles = ['output_csv', 'output_h5ad', 'output_summary', 'comparison_csv']
    .map((key) => {
      const path = normalizedResult?.[key]
      if (typeof path !== 'string') return null
      return { key, href: fileLink(content.project_id, path), name: path.split('/').pop() || path }
    })
    .filter((item): item is { key: string; href: string; name: string } => Boolean(item?.href))

  return (
    <div className="space-y-3 text-[15px] leading-relaxed">
      {summaryText && <MarkdownRenderer content={summaryText} />}
      {showPlaceholder && content.text && <MarkdownRenderer content={content.text} />}

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

      {content.job_id && isRunning && (
        <div className="flex items-center justify-between rounded-lg border border-border-faint bg-surface p-2">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-success" />
            <span>{t('executionLog.running')}</span>
          </div>
          <button
            type="button"
            onClick={handleCancel}
            disabled={cancelling}
            className="inline-flex items-center gap-1 rounded border border-error/40 px-2 py-0.5 text-[10px] font-medium text-error hover:bg-error/5 disabled:opacity-50"
          >
            <Square className="h-3 w-3 fill-current" />
            {cancelling ? '…' : t('workflow.abort')}
          </button>
        </div>
      )}

      {isSuccess && !summaryText && !rich && (
        <div className="rounded-lg border border-success/30 bg-success/5 p-3 text-sm">
          <div className="mb-2 font-medium text-success">{t('executionLog.completed')}</div>
          <div className="space-y-1 text-xs text-foreground/80">
            {normalizedResult!.cells !== undefined && (
              <p>
                细胞数：{normalizedResult!.cells}，基因数：{normalizedResult!.genes}
              </p>
            )}
            {normalizedResult!.comparison?.adjusted_rand_index !== undefined && (
              <p>
                与现有标签的 Adjusted Rand Index：
                {normalizedResult!.comparison.adjusted_rand_index.toFixed(3)}
              </p>
            )}
            {normalizedResult!.model && <p>CellTypist 模型：{normalizedResult!.model}</p>}
            {outputFiles.length > 0 && (
              <div className="mt-2 space-y-0.5">
                <p className="font-medium">输出文件：</p>
                {outputFiles.map((file) => (
                  <a
                    key={file.key}
                    href={file.href}
                    target="_blank"
                    rel="noreferrer"
                    className="block truncate text-primary hover:underline"
                    title={file.name}
                  >
                    {file.name}
                  </a>
                ))}
              </div>
            )}
          </div>
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
      <p className="text-xs font-medium text-foreground/80">产物文件：</p>
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
