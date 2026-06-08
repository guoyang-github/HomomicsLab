import { FlowCanvas } from './FlowCanvas'
import { DetailPanel } from './DetailPanel'

export function Workspace() {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 bg-white px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-800">工作空间</h2>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1">
          <FlowCanvas />
        </div>
        <DetailPanel />
      </div>
    </div>
  )
}
