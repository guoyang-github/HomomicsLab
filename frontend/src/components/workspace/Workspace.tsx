import { useEffect, useState } from 'react'
import { ReactFlowProvider } from 'reactflow'
import { FlowCanvas } from './FlowCanvas'
import { ProvenanceGraph } from './ProvenanceGraph'
import { DetailPanel } from './DetailPanel'
import { ExecutionLogPanel } from './ExecutionLogPanel'
import { PlanEditor } from './PlanEditor'
import { ExecutionSSEConnector } from './ExecutionSSEConnector'
import { usePlanStore } from '@/stores/planStore'
import { useChatStore } from '@/stores/chatStore'
import { useActiveExecutionJob } from '@/hooks/useActiveExecutionJob'
import { useTranslation } from '@/i18n'
import { planApi } from '@/services/api'
import { Info } from 'lucide-react'
import type { PlanRequestContent } from '@/types/chat'

type WorkspaceTab = 'workflow' | 'provenance'

export function Workspace() {
  const { t } = useTranslation()
  const viewMode = usePlanStore((state) => state.viewMode)
  const loadApprovedPlan = usePlanStore((state) => state.loadApprovedPlan)
  const discardDraft = usePlanStore((state) => state.discardDraft)
  const currentSessionId = useChatStore((state) => state.currentSessionId)
  const { job: activeExecutionJob } = useActiveExecutionJob()
  const executionStatus = activeExecutionJob?.status ?? 'idle'
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('workflow')

  // Load the latest approved plan for this session so the workflow view shows
  // the full phase graph even when execution was delegated to a single skill.
  useEffect(() => {
    if (viewMode === 'draft' || !currentSessionId) return
    let cancelled = false
    planApi
      .listPlans(currentSessionId)
      .then((res) => {
        if (cancelled) return
        const plans = (res.data.plans || []) as Array<{
          plan_id: string
          status: string
          version: number
          intent_analysis_type: string
          created_at: string
        }>
        if (plans.length === 0) return
        // Pick the most recent plan for this session.
        const latest = plans.sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        )[0]
        return planApi.getPlan(latest.plan_id)
      })
      .then((res) => {
        if (cancelled || !res) return
        const payload = res.data
        const content: PlanRequestContent = {
          plan_id: payload.plan_id,
          response_text: payload.suggestion_text || payload.rationale_summary || '',
          plan: {
            plan_id: payload.plan_id,
            status: payload.status,
            is_fallback: payload.is_fallback,
            intent_analysis_type: payload.intent_analysis_type,
            phases: payload.phases || [],
            transitions: payload.transitions || [],
            gaps: payload.gaps,
            suggestion_text: payload.suggestion_text,
            version: payload.version,
          },
        }
        loadApprovedPlan(content, executionStatus)
      })
      .catch(() => {
        // Fail silently; the task tree fallback will still render.
      })
    return () => {
      cancelled = true
    }
  }, [currentSessionId, viewMode, loadApprovedPlan, executionStatus])

  // When the overlay closes and there is no draft, clear any approved plan view.
  useEffect(() => {
    return () => {
      if (viewMode === 'approved') {
        discardDraft()
      }
    }
  }, [viewMode, discardDraft])

  const isDraft = viewMode === 'draft'
  const showPlanEditor = isDraft && activeTab === 'workflow'

  return (
    <div className="flex h-full flex-col">
      <ExecutionSSEConnector />
      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden">
          {!isDraft && (
            <div className="flex items-center justify-between border-b border-border-faint bg-surface px-4 py-2">
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setActiveTab('workflow')}
                  className={cn(
                    'rounded-md px-3 py-1 text-sm font-medium transition-colors',
                    activeTab === 'workflow'
                      ? 'bg-surface-2 text-accent'
                      : 'text-muted-foreground hover:bg-surface-2 hover:text-foreground'
                  )}
                >
                  {t('workspace.workflow')}
                </button>
              </div>
              <button
                onClick={() => setActiveTab('provenance')}
                className={cn(
                  'inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground',
                  activeTab === 'provenance' && 'bg-surface-2 text-foreground'
                )}
              >
                <Info className="h-3.5 w-3.5" />
                {t('workspace.provenance')}
              </button>
            </div>
          )}

          {activeTab === 'provenance' && !isDraft && (
            <div className="shrink-0 border-b border-border-faint bg-surface px-4 py-2">
              <p className="flex items-start gap-2 text-xs text-muted-foreground">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
                <span>{t('workspace.provenanceHint')}</span>
              </p>
            </div>
          )}

          <div className="flex-1 overflow-hidden">
            {showPlanEditor ? (
              <ReactFlowProvider>
                <PlanEditor />
              </ReactFlowProvider>
            ) : activeTab === 'provenance' && !isDraft ? (
              <ProvenanceGraph />
            ) : (
              <FlowCanvas />
            )}
          </div>
          <ExecutionLogPanel />
        </div>
        {!isDraft && <DetailPanel />}
      </div>
    </div>
  )
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(' ')
}
