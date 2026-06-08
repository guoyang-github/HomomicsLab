import { useEffect } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  type NodeProps,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { useTaskStore } from '@/stores/taskStore'
import type { TaskNode } from '@/types/tasks'

const statusColors: Record<TaskNode['status'], string> = {
  pending: '#94a3b8',
  running: '#2563eb',
  completed: '#16a34a',
  failed: '#dc2626',
  awaiting_human: '#eab308',
  aborted: '#64748b',
}

function TaskNodeComponent({ data, selected }: NodeProps<TaskNode>) {
  const selectTask = useTaskStore((state) => state.selectTask)

  return (
    <div
      onClick={() => selectTask(data.id)}
      className={`rounded-lg border-2 bg-white p-3 shadow-sm cursor-pointer ${
        selected ? 'border-primary' : 'border-slate-200'
      }`}
      style={{ borderLeftColor: statusColors[data.status], borderLeftWidth: 4 }}
    >
      <Handle type="target" position={Position.Top} />
      <div className="text-sm font-semibold">{data.name}</div>
      <div className="text-xs text-slate-500">{data.description}</div>
      <div className="mt-1 text-xs font-medium" style={{ color: statusColors[data.status] }}>
        {data.status}
      </div>

      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

const nodeTypes = {
  task: TaskNodeComponent,
}

export function FlowCanvas() {
  const tasks = useTaskStore((state) => state.tasks)
  const selectedTaskId = useTaskStore((state) => state.selectedTaskId)

  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  useEffect(() => {
    const newNodes = tasks.map((task, index) => ({
      id: task.id,
      type: 'task',
      position: { x: 100 + (index % 3) * 250, y: 100 + Math.floor(index / 3) * 150 },
      data: task,
      selected: task.id === selectedTaskId,
    }))

    const newEdges = tasks.flatMap((task) =>
      task.dependencies.map((depId) => ({
        id: `e-${depId}-${task.id}`,
        source: depId,
        target: task.id,
        animated: task.status === 'running',
        style: { stroke: statusColors[task.status] },
      }))
    )

    setNodes(newNodes)
    setEdges(newEdges)
  }, [tasks, selectedTaskId])

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap nodeStrokeWidth={3} />
      </ReactFlow>
    </div>
  )
}
