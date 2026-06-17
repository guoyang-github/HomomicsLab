import { useEffect, useState } from 'react'
import { clsx } from 'clsx'
import { Clock, GitCompare } from 'lucide-react'
import { planApi } from '@/services/api'
import { useChatStore } from '@/stores/chatStore'
import { useTranslation } from '@/i18n'
import { Card, CardHeader, CardTitle, CardContent, Badge } from '@/components/ui'

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
  const { t } = useTranslation()
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
    return <p className="text-sm text-muted-foreground">{t('planHistory.startSession')}</p>
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Clock className="h-4 w-4 text-primary" />
          {t('planHistory.title')}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading && <p className="text-xs text-muted-foreground">{t('common.loading')}</p>}
        <ul className="space-y-1.5">
          {plans.map((plan) => (
            <li
              key={plan.plan_id}
              onClick={() => loadDiff(plan.plan_id)}
              className={clsx(
                'cursor-pointer rounded-lg border p-2.5 text-xs transition-colors',
                selectedPlanId === plan.plan_id
                  ? 'border-primary/30 bg-primary/5'
                  : 'border-border bg-card hover:bg-muted/50'
              )}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-foreground">{plan.intent_analysis_type}</span>
                <Badge variant="outline" size="sm">{plan.status}</Badge>
              </div>
              <div className="mt-1 text-muted-foreground">
                {t('plan.versionLabel', { version: plan.version })} · {new Date(plan.created_at).toLocaleString()}
              </div>
            </li>
          ))}
        </ul>

        {diff && diff.differences.length > 0 && (
          <div className="rounded-lg border border-border bg-card p-3">
            <div className="mb-2 flex items-center gap-2 text-xs font-medium text-foreground">
              <GitCompare className="h-3.5 w-3.5" />
              {t('planHistory.diffTitle')}
            </div>
            <ul className="space-y-1">
              {diff.differences.map((d, idx) => (
                <li key={idx} className="text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{d.phase_type}</span>: {d.change}
                  {d.parameter && ` (${d.parameter})`}
                  {d.old !== undefined && d.new !== undefined && (
                    <span className="ml-1">
                      {String(d.old)} → {String(d.new)}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
