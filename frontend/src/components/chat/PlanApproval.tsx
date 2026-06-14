import { useState } from 'react'
import { planApi } from '@/services/api'
import { useChatStore } from '@/stores/chatStore'
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
      } else {
        await planApi.reject(plan_id)
      }

      addMessage({
        id: `msg_${Date.now()}`,
        type: 'system',
        content: approved ? '已批准计划，开始执行。' : '已拒绝计划。',
        sender: 'system',
        timestamp: new Date().toISOString(),
      })
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
    <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
      <p className="mb-2 text-sm font-medium text-blue-900">📋 分析计划待审批</p>
      <p className="mb-3 text-sm text-blue-800">{response_text}</p>

      <div className="mb-3 space-y-2">
        {plan.phases.map((phase) => (
          <PlanPhaseRow
            key={phase.phase_type}
            phase={phase}
            editing={editing}
            values={params[phase.phase_type] || {}}
            onChange={updateParam}
          />
        ))}
      </div>

      {plan.gaps && plan.gaps.length > 0 && (
        <div className="mb-3 text-xs text-blue-700">
          <p className="font-medium">已知缺口：</p>
          <ul className="list-disc pl-4">
            {plan.gaps.map((gap, idx) => (
              <li key={idx}>
                {String(gap.from_phase)} → {String(gap.to_phase)}: {String(gap.gap_type)}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => handleApprove(true)}
          disabled={isSubmitting}
          className="rounded bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {isSubmitting ? '提交中...' : '批准'}
        </button>
        <button
          onClick={() => handleApprove(false)}
          disabled={isSubmitting}
          className="rounded border border-blue-300 bg-white px-3 py-1.5 text-sm font-medium text-blue-800 hover:bg-blue-100 disabled:opacity-50"
        >
          拒绝
        </button>
        <button
          onClick={() => setEditing(!editing)}
          disabled={isSubmitting || modifiedPhases.length === 0}
          className="rounded border border-blue-300 bg-white px-3 py-1.5 text-sm font-medium text-blue-800 hover:bg-blue-100 disabled:opacity-50"
        >
          {editing ? '完成编辑' : '编辑参数'}
        </button>
      </div>
    </div>
  )
}

interface PhaseRowProps {
  phase: PlanPhase
  editing: boolean
  values: { [key: string]: unknown }
  onChange: (phaseType: string, key: string, value: unknown) => void
}

function PlanPhaseRow({ phase, editing, values, onChange }: PhaseRowProps) {
  const hasParams = phase.parameters && Object.keys(phase.parameters).length > 0

  return (
    <div className="rounded border border-blue-100 bg-white p-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-800">
          {phase.phase_type}
          {phase.required === false && (
            <span className="ml-1 text-xs text-slate-500">(可选)</span>
          )}
        </span>
        <span className="text-xs text-slate-500">{phase.skill_id}</span>
      </div>
      {phase.description && (
        <p className="text-xs text-slate-600">{phase.description}</p>
      )}
      {hasParams && (
        <div className="mt-1 space-y-1">
          {Object.entries(phase.parameters!).map(([key, value]) => {
            const isEdited = key in values && values[key] !== value
            return (
              <div key={key} className="flex items-center gap-2 text-xs">
                <span className="font-medium text-slate-700">{key}:</span>
                {editing && !phase.readonly ? (
                  <input
                    type="text"
                    value={String(values[key] ?? value)}
                    onChange={(e) => {
                      const raw = e.target.value
                      const parsed =
                        typeof value === 'number' ? Number(raw) || raw : raw
                      onChange(phase.phase_type, key, parsed)
                    }}
                    className="rounded border border-slate-300 px-1 py-0.5"
                  />
                ) : (
                  <span className={isEdited ? 'font-medium text-blue-700' : 'text-slate-600'}>
                    {String(values[key] ?? value as unknown)}
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
