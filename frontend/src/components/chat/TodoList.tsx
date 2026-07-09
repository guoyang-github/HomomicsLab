import { useTaskStore } from '@/stores/taskStore'
import { useExecutionStore } from '@/stores/executionStore'
import { useTranslation } from '@/i18n'
import type { TaskNode, TaskProgress } from '@/types/tasks'

interface Props {
  content: {
    text: string
    tasks: TaskNode[]
    progress?: TaskProgress
    job_id?: string
    project_id?: string
    result?: Record<string, any>
    status?: string
  }
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

  const outputFiles = ['output_csv', 'output_h5ad', 'output_summary', 'comparison_csv']
    .map((key) => {
      const path = normalizedResult?.[key]
      if (typeof path !== 'string') return null
      return { key, href: fileLink(content.project_id, path), name: path.split('/').pop() || path }
    })
    .filter((item): item is { key: string; href: string; name: string } => Boolean(item?.href))

  return (
    <div className="space-y-3">
      <p className="text-sm">{content.text}</p>

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
          <div className="mb-1 flex items-center gap-2 text-xs font-medium text-slate-600">
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

      {isSuccess && (
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
