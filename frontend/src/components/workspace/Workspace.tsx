import { FlowCanvas } from './FlowCanvas'
import { DetailPanel } from './DetailPanel'
import { ExecutionLogPanel } from './ExecutionLogPanel'

export function Workspace() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 overflow-hidden">
            <FlowCanvas />
          </div>
          <ExecutionLogPanel />
        </div>
        <DetailPanel />
      </div>
    </div>
  )
}
