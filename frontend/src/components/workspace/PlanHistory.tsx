import { useEffect, useState } from 'react'
import { planApi } from '@/services/api'
import { useChatStore } from '@/stores/chatStore'

interface PlanSummary {
  plan_id: string
  status: string
  version: number
  intent_analysis_type: string
  created_at: string
}

interface DiffItem {
  phase_type: string
  change: string
  parameter?: string
  old?: unknown
  new?: unknown
}

export function PlanHistory() {
  const { currentSessionId } = useChatStore()
  const [plans, setPlans] = useState<PlanSummary[]>([])
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null)
  const [diff, setDiff] = useState<{ plan_a_id: string; plan_b_id: string; differences: DiffItem[] } | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!currentSessionId) return
    setLoading(true)
    planApi
      .listPlans(currentSessionId)
      .then((res) => setPlans(res.data.plans || []))
      .finally(() => setLoading(false))
  }, [currentSessionId])

  const loadDiff = async (planId: string) => {
    const res = await planApi.diff(planId)
    setDiff(res.data)
    setSelectedPlanId(planId)
  }

  if (!currentSessionId) {
    return <p className="text-sm text-slate-500">请先开始一个会话</p>
  }

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium">计划版本历史</h4>
      {loading && <p className="text-xs text-slate-500">加载中...</p>}
      <ul className="space-y-1">
        {plans.map((plan) => (
          <li
            key={plan.plan_id}
            className={`cursor-pointer rounded border p-2 text-xs ${
              selectedPlanId === plan.plan_id ? 'border-blue-400 bg-blue-50' : 'border-slate-200 hover:bg-slate-50'
            }`}
            onClick={() => loadDiff(plan.plan_id)}
          >
            <div className="flex items-center justify-between">
              <span className="font-medium">{plan.intent_analysis_type}</span>
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase">{plan.status}</span>
            </div>
            <div className="mt-1 text-slate-500">版本 {plan.version} • {new Date(plan.created_at).toLocaleString()}</div>
          </li>
        ))}
      </ul>

      {diff && diff.differences.length > 0 && (
        <div className="rounded border border-slate-200 bg-white p-2">
          <h5 className="mb-1 text-xs font-medium">与上一版本差异</h5>
          <ul className="space-y-1">
            {diff.differences.map((d, idx) => (
              <li key={idx} className="text-xs text-slate-700">
                <span className="font-medium">{d.phase_type}</span>: {d.change}
                {d.parameter && ` (${d.parameter})`}
                {d.old !== undefined && d.new !== undefined && (
                  <span className="ml-1 text-slate-500">
                    {String(d.old)} → {String(d.new)}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
