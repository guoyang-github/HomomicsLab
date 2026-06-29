import { useState } from 'react'
import { Check, X, Pencil, Layers, Clock, DollarSign } from 'lucide-react'
import { clsx } from 'clsx'
import { planApi } from '@/services/api'
import { usePlanStore } from '@/stores/planStore'
import { useChatStore } from '@/stores/chatStore'
import { useTaskStore } from '@/stores/taskStore'
import { useExecutionStore } from '@/stores/executionStore'
import { useTranslation } from '@/i18n'
import { Button, Badge, Card, CardHeader, CardDescription, CardContent } from '@/components/ui'
import { toastError, toastSuccess } from '@/stores/toastStore'
import type { ExecutionPlanContent, PlanModification, PlanRequestContent } from '@/types/chat'

interface Props {
  content: ExecutionPlanContent
}

export function ExecutionPlan({ content }: Props) {
  const { t } = useTranslation()
  const { plan_id, response_text, tasks, progress, estimates } = content
  const { addMessage } = useChatStore()
  const { setTaskTree, setProgress } = useTaskStore()
  const { setJobId, reset: resetExecution } = useExecutionStore()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [editing, setEditing] = useState(false)
  const [params, setParams] = useState<Record<string, Record<string, unknown>>>(() => {
    const initial: Record<string, Record<string, unknown>> = {}
    tasks.forEach((task) => {
      if (task.parameters && Object.keys(task.parameters).length > 0) {
        initial[task.id] = { ...task.parameters }
      }
    })
    return initial
  })

  const buildModifications = (): PlanModification[] => {
    const modifications: PlanModification[] = []
    tasks.forEach((task) => {
      const edited = params[task.id]
      if (!edited) return
      const original = task.parameters || {}
      Object.entries(edited).forEach(([key, value]) => {
        if (original[key] !== value) {
          modifications.push({
            phase_type: task.id,
            action: 'update',
            parameter: key,
            old_value: original[key],
            new_value: value,
          })
        }
      })
    })
    return modifications
  }

  const parseValue = (raw: string, original: unknown): unknown => {
    if (typeof original === 'number') {
      const num = Number(raw)
      return Number.isNaN(num) ? raw : num
    }
    if (typeof original === 'boolean') {
      return raw === 'true'
    }
    if (raw === 'true') return true
    if (raw === 'false') return false
    if (raw === '') return ''
    const num = Number(raw)
    if (!Number.isNaN(num) && raw.trim() !== '') return num
    return raw
  }

  const isEdited = (taskId: string, key: string, value: unknown) => {
    const original = tasks.find((t) => t.id === taskId)?.parameters?.[key]
    return value !== original
  }

  const handleApprove = async (approved: boolean) => {
    setIsSubmitting(true)
    try {
      const modifications = buildModifications()
      const response =
        modifications.length > 0
          ? await planApi.modify(plan_id, approved, modifications)
          : await planApi.approve(plan_id)

      if (approved) {
        toastSuccess(t('plan.approved'))
        if (response.data.job_id) {
          resetExecution()
          setJobId(response.data.job_id)
          setTaskTree(tasks)
          if (progress) setProgress(progress)
          addMessage({
            id: `msg_${Date.now()}`,
            type: 'todo_list',
            content: {
              text: t('plan.startedExecution'),
              tasks,
              progress,
              job_id: response.data.job_id,
            },
            sender: 'agent',
            timestamp: new Date().toISOString(),
          })
        }
      } else {
        toastSuccess(t('plan.rejected'))
      }
    } catch (error: any) {
      toastError(error?.response?.data?.detail || t('common.submitFailed'))
    } finally {
      setIsSubmitting(false)
    }
  }

  const updateParam = (taskId: string, key: string, value: unknown) => {
    setParams((prev) => ({
      ...prev,
      [taskId]: {
        ...(prev[taskId] || {}),
        [key]: value,
      },
    }))
  }

  const editableTasks = tasks.filter((task) => task.parameters && Object.keys(task.parameters).length > 0)

  const formatDuration = (seconds?: number) => {
    if (seconds === undefined || seconds === null) return null
    if (seconds < 60) return `${Math.round(seconds)}s`
    const mins = Math.floor(seconds / 60)
    const rem = Math.round(seconds % 60)
    return rem > 0 ? `${mins}m ${rem}s` : `${mins}m`
  }

  const formatCost = (cost?: number) => {
    if (cost === undefined || cost === null) return null
    if (cost < 0.001) return `< $0.001`
    return `$${cost.toFixed(2)}`
  }

  const openInEditor = () => {
    const planContent: PlanRequestContent = {
      plan_id,
      response_text,
      plan: {
        plan_id,
        status: 'pending_approval',
        is_fallback: false,
        intent_analysis_type: 'execution_plan',
        phases: tasks.map((task) => ({
          phase_type: task.id,
          description: task.description,
          skill_id: task.skills_required[0],
          parameters: task.parameters,
        })),
        version: 1,
      },
    }
    usePlanStore.getState().loadPlan(planContent)
    addMessage({
      id: `msg_${Date.now()}`,
      type: 'system',
      content: t('plan.openedInEditor'),
      sender: 'system',
      timestamp: new Date().toISOString(),
    })
  }

  return (
    <Card className="border-primary/20 bg-primary/5">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Badge variant="info" size="md">{t('plan.pendingApproval')}</Badge>
        </div>
        <CardDescription className="mt-2 text-foreground/80">{response_text}</CardDescription>
        {(estimates?.total_estimated_duration_seconds !== undefined || estimates?.total_estimated_cost_usd !== undefined) && (
          <div className="mt-3 flex flex-wrap gap-2">
            {estimates?.total_estimated_duration_seconds !== undefined && (
              <Badge variant="outline" size="sm" className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {t('plan.estimatedDuration')}: {formatDuration(estimates.total_estimated_duration_seconds)}
              </Badge>
            )}
            {estimates?.total_estimated_cost_usd !== undefined && (
              <Badge variant="outline" size="sm" className="flex items-center gap-1">
                <DollarSign className="h-3 w-3" />
                {t('plan.estimatedCost')}: {formatCost(estimates.total_estimated_cost_usd)}
              </Badge>
            )}
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          {tasks.map((task, index) => (
            <div key={task.id} className="rounded-lg border border-border bg-card p-3">
              <div className="flex items-center gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">
                  {index + 1}
                </span>
                <span className="text-sm font-semibold text-foreground">{task.name}</span>
                {task.skills_required.length > 0 && (
                  <Badge variant="outline" size="sm">
                    {task.skills_required[0]}
                  </Badge>
                )}
                {task.estimated_duration_minutes !== undefined && task.estimated_duration_minutes > 0 && (
                  <Badge variant="secondary" size="sm" className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatDuration(task.estimated_duration_minutes * 60)}
                  </Badge>
                )}
                {task.estimated_cost_usd !== undefined && (
                  <Badge variant="secondary" size="sm" className="flex items-center gap-1">
                    <DollarSign className="h-3 w-3" />
                    {formatCost(task.estimated_cost_usd)}
                  </Badge>
                )}
              </div>
              {task.description && (
                <p className="mt-1 text-xs text-muted-foreground">{task.description}</p>
              )}
              {editing && params[task.id] && (
                <div className="mt-2 space-y-1.5">
                  {Object.entries(params[task.id]).map(([key, value]) => (
                    <div key={key} className="flex items-center gap-2 text-xs">
                      <span className="min-w-[80px] font-medium text-muted-foreground">{key}</span>
                      <input
                        type="text"
                        value={String(value ?? '')}
                        onChange={(e) => {
                          updateParam(task.id, key, parseValue(e.target.value, value))
                        }}
                        className={clsx(
                          'h-7 flex-1 rounded border px-2 py-1 text-xs',
                          isEdited(task.id, key, value)
                            ? 'border-primary bg-primary/5'
                            : 'border-border bg-background'
                        )}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => handleApprove(true)} loading={isSubmitting}>
            <Check className="mr-1.5 h-4 w-4" />
            {t('plan.approve')}
          </Button>
          <Button variant="outline" onClick={() => handleApprove(false)} disabled={isSubmitting}>
            <X className="mr-1.5 h-4 w-4" />
            {t('plan.reject')}
          </Button>
          {editableTasks.length > 0 && (
            <Button variant="secondary" onClick={() => setEditing(!editing)} disabled={isSubmitting}>
              <Pencil className="mr-1.5 h-4 w-4" />
              {editing ? t('plan.finishEdit') : t('plan.editParams')}
            </Button>
          )}
          <Button variant="outline" onClick={openInEditor} disabled={isSubmitting}>
            <Layers className="mr-1.5 h-4 w-4" />
            {t('plan.canvasEdit')}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
