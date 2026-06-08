import { useTaskStore } from '@/stores/taskStore'
import type { TaskNode, TaskProgress } from '@/types/tasks'

interface Props {
  content: {
    text: string
    tasks: TaskNode[]
    progress?: TaskProgress
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
  const selectTask = useTaskStore((state) => state.selectTask)

  return (
    <div className="space-y-3">
      <p className="text-sm">{content.text}</p>

      {content.progress && (
        <div className="mb-3">
          <div className="mb-1 flex justify-between text-xs text-slate-600">
            <span>进度</span>
            <span>{content.progress.completed}/{content.progress.total}</span>
          </div>
          <div className="h-2 w-full rounded-full bg-slate-200">
            <div
              className="h-2 rounded-full bg-success transition-all"
              style={{ width: `${content.progress.percent}%` }}
            />
          </div>
        </div>
      )}

      <ul className="space-y-1">
        {content.tasks?.map((task) => (
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
