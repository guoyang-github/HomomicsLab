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
            <div className="flex items-center gap-1 border-b border-border bg-card px-4 py-2">
              <button
                onClick={() => setActiveTab('workflow')}
                className={cn(
                  'rounded-md px-3 py-1 text-sm font-medium transition-colors',
                  activeTab === 'workflow'
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
              >
                {t('workspace.workflow')}
              </button>
              <button
                onClick={() => setActiveTab('provenance')}
                className={cn(
                  'rounded-md px-3 py-1 text-sm font-medium transition-colors',
                  activeTab === 'provenance'
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
              >
                {t('workspace.provenance')}
              </button>
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
