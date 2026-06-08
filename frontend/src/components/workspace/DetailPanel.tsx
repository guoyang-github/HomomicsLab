import { useTaskStore } from '@/stores/taskStore'
import { DataUploader } from '@/components/shared/DataUploader'

export function DetailPanel() {
  const selectedTaskId = useTaskStore((state) => state.selectedTaskId)
  const tasks = useTaskStore((state) => state.tasks)

  const task = tasks.find((t) => t.id === selectedTaskId)

  if (!task) {
    return (
      <div className="w-72 border-l border-slate-200 bg-slate-50 p-4">
        <p className="mb-4 text-sm text-slate-500">点击节点查看详情，或上传数据开始分析</p>
        <DataUploader />
      </div>
    )
  }

  return (
    <div className="w-72 overflow-y-auto border-l border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-lg font-semibold">{task.name}</h3>
      <p className="mb-4 text-sm text-slate-600">{task.description}</p>

      <div className="mb-4 space-y-2 text-sm">
        <div>
          <span className="font-medium">状态: </span>
          <span className="rounded px-2 py-0.5 text-xs bg-slate-100">{task.status}</span>
        </div>
        <div>
          <span className="font-medium">阶段: </span>
          {task.phase}
        </div>
        <div>
          <span className="font-medium">预计耗时: </span>
          {task.estimated_duration_minutes} 分钟
        </div>
        {task.skills_required.length > 0 && (
          <div>
            <span className="font-medium">所需 Skills: </span>
            {task.skills_required.join(', ')}
          </div>
        )}
      </div>

      {task.parameters && Object.keys(task.parameters).length > 0 && (
        <div className="mb-4">
          <h4 className="mb-2 text-sm font-medium">参数</h4>
          <pre className="rounded bg-slate-50 p-2 text-xs">
            {JSON.stringify(task.parameters, null, 2)}
          </pre>
        </div>
      )}

      {task.result && (
        <div className="mb-4">
          <h4 className="mb-2 text-sm font-medium">结果</h4>
          <pre className="rounded bg-slate-50 p-2 text-xs">
            {JSON.stringify(task.result, null, 2)}
          </pre>
        </div>
      )}

      {task.error_message && (
        <div className="mb-4">
          <h4 className="mb-2 text-sm font-medium text-error">错误</h4>
          <p className="text-xs text-error">{task.error_message}</p>
        </div>
      )}
    </div>
  )
}
