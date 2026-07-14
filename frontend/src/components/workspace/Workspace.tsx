import { useState } from 'react'
import { ReactFlowProvider } from 'reactflow'
import { FlowCanvas } from './FlowCanvas'
import { ProvenanceGraph } from './ProvenanceGraph'
import { DetailPanel } from './DetailPanel'
import { ExecutionLogPanel } from './ExecutionLogPanel'
import { PlanEditor } from './PlanEditor'
import { ExecutionSSEConnector } from './ExecutionSSEConnector'
import { usePlanStore } from '@/stores/planStore'
import { useTranslation } from '@/i18n'
import { Info } from 'lucide-react'

type WorkspaceTab = 'workflow' | 'provenance'

export function Workspace() {
  const { t } = useTranslation()
  const hasDraftPlan = usePlanStore((state) => state.draftPlan !== null)
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('workflow')

  // When a draft plan appears, keep the workflow tab in focus.
  const showPlanEditor = hasDraftPlan && activeTab === 'workflow'

  return (
    <div className="flex h-full flex-col">
      <ExecutionSSEConnector />
      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden">
          {!hasDraftPlan && (
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

          {activeTab === 'provenance' && !hasDraftPlan && (
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
            ) : activeTab === 'provenance' && !hasDraftPlan ? (
              <ProvenanceGraph />
            ) : (
              <FlowCanvas />
            )}
          </div>
          <ExecutionLogPanel />
        </div>
        {!hasDraftPlan && <DetailPanel />}
      </div>
    </div>
  )
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(' ')
}
