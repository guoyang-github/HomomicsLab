import { ReactFlowProvider } from 'reactflow'
import { FlowCanvas } from './FlowCanvas'
import { DetailPanel } from './DetailPanel'
import { ExecutionLogPanel } from './ExecutionLogPanel'
import { PlanEditor } from './PlanEditor'
import { usePlanStore } from '@/stores/planStore'

export function Workspace() {
  const hasDraftPlan = usePlanStore((state) => state.draftPlan !== null)

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 overflow-hidden">
            {hasDraftPlan ? (
              <ReactFlowProvider>
                <PlanEditor />
              </ReactFlowProvider>
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
