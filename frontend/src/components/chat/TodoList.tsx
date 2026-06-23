import { useTaskStore } from '@/stores/taskStore'
import { useTranslation } from '@/i18n'
import type { TaskNode, TaskProgress } from '@/types/tasks'

interface Props {
  content: {
    text: string
    tasks: TaskNode[]
    progress?: TaskProgress
    job_id?: string
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

export function TodoList({ content }: Props) {
  const { t } = useTranslation()
  const selectTask = useTaskStore((state) => state.selectTask)
  const liveTasks = useTaskStore((state) => state.tasks)
  const liveProgress = useTaskStore((state) => state.progress)
  const hasLiveTasks = liveTasks.length > 0 && content.job_id
  const tasks = hasLiveTasks ? liveTasks : content.tasks
  const progress = hasLiveTasks ? liveProgress : content.progress

  return (
    <div className="space-y-3">
      <p className="text-sm">{content.text}</p>

      {progress && progress.total > 0 && (
        <div className="mb-3">
          <div className="mb-1 flex justify-between text-xs text-slate-600">
            <span>{t('plan.progress')}</span>
            <span>{progress.completed}/{progress.total}</span>
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
    </div>
  )
}
