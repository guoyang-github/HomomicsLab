import { Download, FileText, Square } from 'lucide-react'
import { useState } from 'react'
import { useTaskStore } from '@/stores/taskStore'
import { useExecutionStore } from '@/stores/executionStore'
import { useTranslation } from '@/i18n'
import type { TaskNode, TaskProgress } from '@/types/tasks'
import { MarkdownRenderer } from '@/components/shared/MarkdownRenderer'
import { fileApi, executionApi } from '@/sdk'
import type { Artifact } from '@/components/artifacts'

interface Props {
  content: {
    text: string
    tasks: TaskNode[]
    progress?: TaskProgress
    job_id?: string
    project_id?: string
    result?: Record<string, any>
    status?: string
    artifacts?: Artifact[]
  }
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
  return typeof text === 'string' && /\*\*(关键指标|关键发现|解读|CellTypist|注释结果|一致性比较|结果)\*\*/.test(text)
}

const statusIcons: Record<TaskNode['status'], string> = {
  pending: '⬜',
  running: '▶️',
  completed: '✅',
  failed: '❌',
  awaiting_human: '⏸️',
  aborted: '🚫',
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

function fileLink(projectId: string | undefined, path: string): string | null {
  if (!projectId || !path) return null
  // Path may be absolute; derive the workspace-relative path.
  const marker = `/workspaces/${projectId}/`
  const idx = path.indexOf(marker)
  const rel = idx >= 0 ? path.slice(idx + marker.length) : path.replace(/^.*\/(outputs|results|data)\//, '$1/')
  return `/files/${projectId}/${rel}`
}

export function TodoList({ content }: Props) {
  const { t } = useTranslation()
  const selectTask = useTaskStore((state) => state.selectTask)
  const liveTasks = useTaskStore((state) => state.tasks)
  const liveProgress = useTaskStore((state) => state.progress)
  const executionStatus = useExecutionStore((state) => state.status)
  const executionLogs = useExecutionStore((state) => state.logs)
  const isConnected = useExecutionStore((state) => state.isConnected)
  const executionResult = useExecutionStore((state) => state.result)
  const hasLiveTasks = liveTasks.length > 0 && content.job_id
  const tasks = hasLiveTasks ? liveTasks : content.tasks
  const progress = hasLiveTasks ? liveProgress : content.progress

  const isRunning = executionStatus === 'running' && content.job_id
  const recentLogs = executionLogs.slice(-5)

  // Prefer the persisted result embedded in the message; fall back to the
  // live execution-store result for real-time updates. Some backend paths
  // nest the result inside the completed task tree rather than a top-level
  // result field.
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
      // Ignore; the SSE will reflect the terminal state anyway.
    }
  }

  const outputFiles = ['output_csv', 'output_h5ad', 'output_summary', 'comparison_csv']
    .map((key) => {
      const path = normalizedResult?.[key]
      if (typeof path !== 'string') return null
      return { key, href: fileLink(content.project_id, path), name: path.split('/').pop() || path }
    })
    .filter((item): item is { key: string; href: string; name: string } => Boolean(item?.href))

  const artifacts: Artifact[] = Array.isArray(normalizedResult?.artifacts)
    ? (normalizedResult!.artifacts as Artifact[])
    : []

  const rich = isRichSummary(content.text)
  const messageArtifacts: Artifact[] =
    artifacts.length > 0 ? artifacts : Array.isArray(content.artifacts) ? content.artifacts : []

  // Backend may embed the rich summary inside final_output.summary. Prefer it
  // over the legacy one-line text so the chat renders the full interpretation.
  const summaryText =
    normalizedResult?.final_output?.summary ||
    normalizedResult?.summary ||
    (rich ? content.text : '')

  const renderArtifactLinks = (items: Artifact[]) => {
    if (items.length === 0) return null
    return (
      <div className="mt-2 space-y-1">
        <p className="text-xs font-medium text-slate-600">产物文件：</p>
        {items.map((artifact, idx) => {
          const href = artifactLink(content.project_id, artifact)
          const name = artifact.name || artifact.path?.split('/').pop() || `file-${idx}`
          const size = formatSize(artifact.size)
          return (
            <div
              key={`${artifact.path || name}-${idx}`}
              className="flex items-center gap-2 rounded border border-border bg-muted/30 px-3 py-1.5 text-xs"
            >
              <FileText className="h-3.5 w-3.5 flex-shrink-0 text-slate-400" />
              <span className="flex-1 truncate" title={name}>
                {name}
              </span>
              {size && <span className="text-[10px] text-slate-400">{size}</span>}
              {href && (
                <a
                  href={href}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-primary hover:underline"
                >
                  <Download className="h-3.5 w-3.5" /> 下载
                </a>
              )}
            </div>
          )
        })}
      </div>
    )
  }

  // If we have a rich summary, do not also render the initial queue placeholder.
  const showPlaceholder = !summaryText && content.text

  return (
    <div className="space-y-3">
      {summaryText && <MarkdownRenderer content={summaryText} />}
      {showPlaceholder && content.text && <MarkdownRenderer content={content.text} />}

      {progress && progress.total > 0 && (
        <div className="mb-3">
          <div className="mb-1 flex justify-between text-xs text-slate-600">
            <span>{t('plan.progress')}</span>
            <span>
              {progress.completed}/{progress.total}
            </span>
          </div>
          <div className="h-2 w-full rounded-full bg-slate-200">
            <div
              className="h-2 rounded-full bg-success transition-all"
              style={{ width: `${progress.percent}%` }}
            />
          </div>
        </div>
      )}

      <ul className="space-y-1">
        {tasks?.map((task) => (
          <li
            key={task.id}
            onClick={() => selectTask(task.id)}
            className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm hover:bg-slate-100"
          >
            <span>{statusIcons[task.status]}</span>
            <span className="flex-1">{task.description}</span>
            <span className="text-xs text-slate-500">{task.phase}</span>
          </li>
        ))}
      </ul>

      {content.job_id && (
        <div className="rounded border border-border bg-card/50 p-2">
          <div className="mb-1 flex items-center justify-between text-xs font-medium text-slate-600">
            <div className="flex items-center gap-2">
              {isRunning ? (
                <>
                  <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-success" />
                  <span>执行中</span>
                </>
              ) : (
                <>
                  <span className="inline-block h-2 w-2 rounded-full bg-slate-400" />
                  <span>等待/已完成</span>
                </>
              )}
              {isConnected && <span className="text-success">● 实时连接</span>}
            </div>
            {isRunning && (
              <button
                type="button"
                onClick={handleCancel}
                disabled={cancelling}
                className="inline-flex items-center gap-1 rounded border border-error/40 px-2 py-0.5 text-[10px] font-medium text-error hover:bg-error/5 disabled:opacity-50"
              >
                <Square className="h-3 w-3 fill-current" />
                {cancelling ? '停止中…' : '停止执行'}
              </button>
            )}
          </div>
          {recentLogs.length > 0 && (
            <ul className="space-y-0.5 font-mono text-[10px] text-slate-500">
              {recentLogs.map((log) => (
                <li key={log.id} className="truncate">
                  <span className="text-slate-400">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>{' '}
                  {log.message}
                </li>
              ))}
            </ul>
          )}
          {recentLogs.length === 0 && isRunning && (
            <p className="text-[10px] text-slate-400">已建立实时连接，正在接收执行事件…</p>
          )}
        </div>
      )}

      {isSuccess && !summaryText && !rich && (
        <div className="rounded border border-success/30 bg-success/5 p-3">
          <div className="mb-2 text-sm font-medium text-success">执行完成</div>
          <div className="space-y-1 text-xs text-slate-700">
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
      {isSuccess && renderArtifactLinks(messageArtifacts)}

      {isFailure && (
        <div className="rounded border border-error/30 bg-error/5 p-3">
          <div className="mb-1 text-sm font-medium text-error">执行失败</div>
          <p className="text-xs text-slate-700">
            {failureMessage || '请查看执行日志了解详情。'}
          </p>
        </div>
      )}
    </div>
  )
}
