import { useTaskStore } from '@/stores/taskStore'
import { PlanHistory } from './PlanHistory'
import { Badge, Card, CardHeader, CardTitle, CardContent, Separator } from '@/components/ui'
import { useTranslation } from '@/i18n'
import {
  Clock,
  Layers,
  Wrench,
  AlertCircle,
} from 'lucide-react'

const statusConfig: Record<string, { labelKey: string; variant: any }> = {
  pending: { labelKey: 'taskStatus.pending', variant: 'secondary' },
  running: { labelKey: 'taskStatus.running', variant: 'info' },
  completed: { labelKey: 'taskStatus.completed', variant: 'success' },
  failed: { labelKey: 'taskStatus.failed', variant: 'error' },
  awaiting_human: { labelKey: 'taskStatus.awaitingHuman', variant: 'warning' },
  aborted: { labelKey: 'taskStatus.aborted', variant: 'secondary' },
}

export function DetailPanel() {
  const { t } = useTranslation()
  const selectedTaskId = useTaskStore((state) => state.selectedTaskId)
  const tasks = useTaskStore((state) => state.tasks)
  const task = tasks.find((t) => t.id === selectedTaskId)

  if (!task) {
    return (
      <div className="w-80 overflow-y-auto border-l border-border bg-card p-4">
        <div className="rounded-lg border border-border bg-muted/50 p-4 text-center">
          <p className="text-sm text-muted-foreground">{t('detail.selectHint')}</p>
        </div>
        <div className="mt-6">
          <PlanHistory />
        </div>
      </div>
    )
  }

  const status = statusConfig[task.status] || { labelKey: undefined, variant: 'secondary' }

  return (
    <div className="w-80 overflow-y-auto border-l border-border bg-card p-4">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-foreground">{task.name}</h3>
          <p className="mt-1 text-xs text-muted-foreground">{task.id}</p>
        </div>
        <Badge variant={status.variant} size="md">{status.labelKey ? t(status.labelKey) : task.status}</Badge>
      </div>

      <p className="mb-4 text-sm text-muted-foreground">{task.description}</p>

      <Card className="mb-4">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">{t('detail.basicInfo')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <Layers className="h-3.5 w-3.5" />
              {t('detail.phase')}
            </span>
            <span className="font-medium">{task.phase}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              {t('detail.estimatedDuration')}
            </span>
            <span className="font-medium">{t('detail.minutes', { minutes: task.estimated_duration_minutes })}</span>
          </div>
          {task.skills_required.length > 0 && (
            <div className="flex items-start justify-between gap-2">
              <span className="flex items-center gap-1.5 text-muted-foreground">
                <Wrench className="h-3.5 w-3.5" />
                {t('detail.requiredSkills')}
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
            <CardTitle className="text-sm">{t('detail.parameters')}</CardTitle>
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
            <CardTitle className="text-sm">{t('detail.result')}</CardTitle>
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
              {t('detail.error')}
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
