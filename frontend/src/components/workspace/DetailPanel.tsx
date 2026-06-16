import { useTaskStore } from '@/stores/taskStore'
import { DataUploader } from '@/components/shared/DataUploader'
import { PlanHistory } from './PlanHistory'
import { Button, Badge, Card, CardHeader, CardTitle, CardContent, Separator } from '@/components/ui'
import {
  Play,
  RotateCcw,
  SkipForward,
  Square,
  Clock,
  Layers,
  Wrench,
  AlertCircle,
} from 'lucide-react'

const statusConfig: Record<string, { label: string; variant: any }> = {
  pending: { label: '待执行', variant: 'secondary' },
  running: { label: '执行中', variant: 'info' },
  completed: { label: '已完成', variant: 'success' },
  failed: { label: '失败', variant: 'error' },
  awaiting_human: { label: '待确认', variant: 'warning' },
  aborted: { label: '已中止', variant: 'secondary' },
}

export function DetailPanel() {
  const selectedTaskId = useTaskStore((state) => state.selectedTaskId)
  const tasks = useTaskStore((state) => state.tasks)
  const task = tasks.find((t) => t.id === selectedTaskId)

  if (!task) {
    return (
      <div className="w-80 overflow-y-auto border-l border-border bg-card p-4">
        <div className="mb-4 rounded-lg border border-border bg-muted/50 p-4 text-center">
          <p className="text-sm text-muted-foreground">点击节点查看详情，或上传数据开始分析</p>
        </div>
        <DataUploader />
        <div className="mt-6">
          <PlanHistory />
        </div>
      </div>
    )
  }

  const status = statusConfig[task.status] || { label: task.status, variant: 'secondary' }

  return (
    <div className="w-80 overflow-y-auto border-l border-border bg-card p-4">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-foreground">{task.name}</h3>
          <p className="mt-1 text-xs text-muted-foreground">{task.id}</p>
        </div>
        <Badge variant={status.variant} size="md">{status.label}</Badge>
      </div>

      <p className="mb-4 text-sm text-muted-foreground">{task.description}</p>

      <div className="mb-4 flex flex-wrap gap-2">
        <Button size="sm" variant="secondary">
          <Play className="mr-1 h-3.5 w-3.5" />
          运行
        </Button>
        <Button size="sm" variant="outline">
          <RotateCcw className="mr-1 h-3.5 w-3.5" />
          重试
        </Button>
        <Button size="sm" variant="outline">
          <SkipForward className="mr-1 h-3.5 w-3.5" />
          跳过
        </Button>
        <Button size="sm" variant="outline">
          <Square className="mr-1 h-3.5 w-3.5" />
          中止
        </Button>
      </div>

      <Card className="mb-4">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">基本信息</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <Layers className="h-3.5 w-3.5" />
              阶段
            </span>
            <span className="font-medium">{task.phase}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              预计耗时
            </span>
            <span className="font-medium">{task.estimated_duration_minutes} 分钟</span>
          </div>
          {task.skills_required.length > 0 && (
            <div className="flex items-start justify-between gap-2">
              <span className="flex items-center gap-1.5 text-muted-foreground">
                <Wrench className="h-3.5 w-3.5" />
                所需 Skills
              </span>
              <div className="flex flex-wrap justify-end gap-1">
                {task.skills_required.map((skill) => (
                  <Badge key={skill} variant="outline" size="sm">
                    {skill}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {task.parameters && Object.keys(task.parameters).length > 0 && (
        <Card className="mb-4">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">参数</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="max-h-48 overflow-auto rounded-lg bg-muted p-3 text-xs">
              {JSON.stringify(task.parameters, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}

      {task.result && (
        <Card className="mb-4">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">结果</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="max-h-48 overflow-auto rounded-lg bg-muted p-3 text-xs">
              {JSON.stringify(task.result, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}

      {task.error_message && (
        <Card className="mb-4 border-error/30 bg-error/5">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm text-error">
              <AlertCircle className="h-4 w-4" />
              错误
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-error">{task.error_message}</p>
          </CardContent>
        </Card>
      )}

      <Separator className="my-4" />
      <PlanHistory />
    </div>
  )
}
