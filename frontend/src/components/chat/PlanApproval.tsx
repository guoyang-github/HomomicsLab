import { useState } from 'react'
import { clsx } from 'clsx'
import { Check, X, Pencil, AlertCircle } from 'lucide-react'
import { planApi } from '@/services/api'
import { useChatStore } from '@/stores/chatStore'
import { Button, Badge, Card, CardHeader, CardDescription, CardContent } from '@/components/ui'
import { toastError, toastSuccess } from '@/stores/toastStore'
import type { PlanRequestContent, PlanPhase } from '@/types/chat'

interface Props {
  content: PlanRequestContent
}

interface EditableParams {
  [phaseType: string]: {
    [key: string]: unknown
  }
}

export function PlanApproval({ content }: Props) {
  const { plan_id, response_text, plan } = content
  const { addMessage } = useChatStore()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [editing, setEditing] = useState(false)
  const [params, setParams] = useState<EditableParams>(() => {
    const initial: EditableParams = {}
    plan.phases.forEach((phase) => {
      if (!phase.readonly && phase.parameters) {
        initial[phase.phase_type] = { ...phase.parameters }
      }
    })
    return initial
  })

  const modifiedPhases = plan.phases.filter((phase) => phase.phase_type in params)

  const buildModifications = (): Array<{
    phase_type: string
    parameter: string
    old_value: unknown
    new_value: unknown
    action: string
  }> => {
    const modifications: Array<{
      phase_type: string
      parameter: string
      old_value: unknown
      new_value: unknown
      action: string
    }> = []
    plan.phases.forEach((phase) => {
      const edited = params[phase.phase_type]
      if (!edited) return
      const original = phase.parameters || {}
      Object.entries(edited).forEach(([key, value]) => {
        if (original[key] !== value) {
          modifications.push({
            phase_type: phase.phase_type,
            parameter: key,
            old_value: original[key],
            new_value: value,
            action: 'update',
          })
        }
      })
    })
    return modifications
  }

  const handleApprove = async (approved: boolean) => {
    setIsSubmitting(true)
    try {
      if (approved) {
        const modifications = buildModifications()
        if (modifications.length > 0) {
          await planApi.modify(plan_id, true, modifications)
        } else {
          await planApi.approve(plan_id)
        }
        toastSuccess('计划已批准，开始执行')
      } else {
        await planApi.reject(plan_id)
        toastSuccess('计划已拒绝')
      }

      addMessage({
        id: `msg_${Date.now()}`,
        type: 'system',
        content: approved ? '已批准计划，开始执行。' : '已拒绝计划。',
        sender: 'system',
        timestamp: new Date().toISOString(),
      })
    } catch (error: any) {
      toastError(error?.response?.data?.detail || '提交失败')
    } finally {
      setIsSubmitting(false)
    }
  }

  const updateParam = (phaseType: string, key: string, value: unknown) => {
    setParams((prev) => ({
      ...prev,
      [phaseType]: {
        ...prev[phaseType],
        [key]: value,
      },
    }))
  }

  return (
    <Card className="border-primary/20 bg-primary/5">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Badge variant="info" size="md">计划待审批</Badge>
          {plan.is_fallback && <Badge variant="warning" size="sm">fallback</Badge>}
        </div>
        <CardDescription className="mt-2 text-foreground/80">{response_text}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          {plan.phases.map((phase, index) => (
            <PlanPhaseRow
              key={phase.phase_type}
              index={index + 1}
              phase={phase}
              editing={editing}
              values={params[phase.phase_type] || {}}
              onChange={updateParam}
            />
          ))}
        </div>

        {plan.gaps && plan.gaps.length > 0 && (
          <div className="rounded-lg border border-warning/20 bg-warning/10 p-3 text-sm text-warning-foreground">
            <div className="mb-1 flex items-center gap-2 font-medium">
              <AlertCircle className="h-4 w-4" />
              已知缺口
            </div>
            <ul className="list-disc space-y-1 pl-4 text-xs">
              {plan.gaps.map((gap, idx) => (
                <li key={idx}>
                  {String(gap.from_phase)} → {String(gap.to_phase)}: {String(gap.gap_type)}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => handleApprove(true)} loading={isSubmitting}>
            <Check className="mr-1.5 h-4 w-4" />
            批准
          </Button>
          <Button variant="outline" onClick={() => handleApprove(false)} disabled={isSubmitting}>
            <X className="mr-1.5 h-4 w-4" />
            拒绝
          </Button>
          <Button
            variant="secondary"
            onClick={() => setEditing(!editing)}
            disabled={isSubmitting || modifiedPhases.length === 0}
          >
            <Pencil className="mr-1.5 h-4 w-4" />
            {editing ? '完成编辑' : '编辑参数'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

interface PhaseRowProps {
  index: number
  phase: PlanPhase
  editing: boolean
  values: { [key: string]: unknown }
  onChange: (phaseType: string, key: string, value: unknown) => void
}

function PlanPhaseRow({ index, phase, editing, values, onChange }: PhaseRowProps) {
  const hasParams = phase.parameters && Object.keys(phase.parameters).length > 0

  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">
            {index}
          </span>
          <span className="text-sm font-semibold text-foreground">{phase.phase_type}</span>
          {phase.required === false && (
            <Badge variant="secondary" size="sm">可选</Badge>
          )}
        </div>
        {phase.skill_id && <Badge variant="outline" size="sm">{phase.skill_id}</Badge>}
      </div>
      {phase.description && (
        <p className="mt-1 text-xs text-muted-foreground">{phase.description}</p>
      )}
      {hasParams && (
        <div className="mt-2 space-y-1.5">
          {Object.entries(phase.parameters!).map(([key, value]) => {
            const isEdited = key in values && values[key] !== value
            return (
              <div key={key} className="flex items-center gap-2 text-xs">
                <span className="min-w-[80px] font-medium text-muted-foreground">{key}</span>
                {editing && !phase.readonly ? (
                  <input
                    type="text"
                    value={String(values[key] ?? value)}
                    onChange={(e) => {
                      const raw = e.target.value
                      const parsed = typeof value === 'number' ? Number(raw) || raw : raw
                      onChange(phase.phase_type, key, parsed)
                    }}
                    className="h-7 flex-1 rounded border border-border bg-background px-2 py-1 text-xs"
                  />
                ) : (
                  <span className={clsx('font-mono', isEdited ? 'font-medium text-primary' : 'text-foreground')}>
                    {String(values[key] ?? (value as unknown))}
                  </span>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
