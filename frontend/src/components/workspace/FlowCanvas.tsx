import { useEffect, useMemo } from 'react'
import { clsx } from 'clsx'
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
import {
  Square,
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  Workflow,
} from 'lucide-react'
import { useTaskStore } from '@/stores/taskStore'
import { usePlanStore } from '@/stores/planStore'
import { useActiveExecutionJob } from '@/hooks/useActiveExecutionJob'
import { buildPhaseTasks, type PhaseFlowTask } from '@/utils/workflowPhases'
import { Badge } from '@/components/ui'
import { useTranslation } from '@/i18n'
import type { TaskNode, TaskStatus } from '@/types/tasks'

const statusConfig: Record<
  TaskStatus,
  { color: string; bg: string; border: string; icon: React.ElementType; labelKey: string }
> = {
  pending: {
    color: 'text-slate-500',
    bg: 'bg-slate-100 dark:bg-slate-800',
    border: 'border-slate-300 dark:border-slate-700',
    icon: Clock,
    labelKey: 'taskStatus.pending',
  },
  running: {
    color: 'text-primary',
    bg: 'bg-primary/10',
    border: 'border-primary',
    icon: Loader2,
    labelKey: 'taskStatus.running',
  },
  completed: {
    color: 'text-success',
    bg: 'bg-success/10',
    border: 'border-success',
    icon: CheckCircle2,
    labelKey: 'taskStatus.completed',
  },
  failed: {
    color: 'text-error',
    bg: 'bg-error/10',
    border: 'border-error',
    icon: AlertCircle,
    labelKey: 'taskStatus.failed',
  },
  awaiting_human: {
    color: 'text-warning',
    bg: 'bg-warning/10',
    border: 'border-warning',
    icon: AlertCircle,
    labelKey: 'taskStatus.awaitingHuman',
  },
  aborted: {
    color: 'text-slate-500',
    bg: 'bg-slate-100 dark:bg-slate-800',
    border: 'border-slate-300 dark:border-slate-700',
    icon: Square,
    labelKey: 'taskStatus.aborted',
  },
}

function TaskNodeComponent({ data, selected }: NodeProps<PhaseFlowTask>) {
  const { t } = useTranslation()
  const selectTask = useTaskStore((state) => state.selectTask)
  const isApprovedPlan = usePlanStore((state) => state.viewMode) === 'approved'
  const config = statusConfig[data.status]
  const Icon = config.icon
  // Phase nodes belong to the execution store (not the plan), so they stay
  // selectable even while an approved plan view is loaded.
  const selectable = data.fromPhase || !isApprovedPlan

  return (
    <div
      onClick={() => selectable && selectTask(data.id)}
      className={clsx(
        'relative min-w-[180px] max-w-[260px] cursor-pointer rounded-xl border-2 bg-card p-4 shadow-card transition-all',
        selected ? 'ring-2 ring-primary ring-offset-2' : '',
        config.border,
        data.status === 'running' && 'animate-pulse-slow'
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-border" />

      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="text-sm font-semibold text-foreground">{data.name}</div>
          {data.description && (
            <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">{data.description}</div>
          )}
        </div>
        <div className={clsx('rounded-full p-1.5', config.bg)}>
          <Icon className={clsx('h-4 w-4', config.color, data.status === 'running' && 'animate-spin')} />
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between">
        <Badge variant={data.status === 'running' ? 'info' : data.status === 'completed' ? 'success' : data.status === 'failed' ? 'error' : 'secondary'} size="sm">
          {t(config.labelKey)}
        </Badge>
        {!data.fromPhase && (
          <span className="text-[10px] text-muted-foreground">{data.estimated_duration_minutes} min</span>
        )}
      </div>

      {data.error_message && (
        <div className="mt-2 rounded bg-error/10 p-1.5 text-[10px] text-error line-clamp-2">
          {data.error_message}
        </div>
      )}

      <Handle type="source" position={Position.Bottom} className="!bg-border" />
    </div>
  )
}

const nodeTypes = {
  task: TaskNodeComponent,
}

interface SubtaskSpec {
  id: string
  description: string
  analysis_type?: string
}

function collectSubtasks(task: TaskNode): SubtaskSpec[] | null {
  const raw = task.parameters?.display_subtasks
  if (!Array.isArray(raw) || raw.length < 2) return null
  return raw.filter(
    (s): s is SubtaskSpec =>
      typeof s === 'object' &&
      s !== null &&
      typeof (s as SubtaskSpec).id === 'string' &&
      typeof (s as SubtaskSpec).description === 'string'
  )
}

function expandTasks(tasks: TaskNode[]): TaskNode[] {
  const out: TaskNode[] = []
  for (const task of tasks) {
    const subtasks = collectSubtasks(task)
    if (!subtasks || subtasks.length === 0) {
      out.push(task)
      continue
    }
    // Replace a parent task with its display subtasks chained sequentially so
    // the workflow view reflects the real execution steps.
    let previousId: string | null = null
    for (const sub of subtasks) {
      const id = `${task.id}::${sub.id}`
      const dependencies = previousId ? [previousId] : task.dependencies
      out.push({
        ...task,
        id,
        name: sub.description,
        description: sub.description,
        dependencies,
        parameters: { ...task.parameters, analysis_type: sub.analysis_type },
      })
      previousId = id
    }
  }
  return out
}

export function FlowCanvas() {
  const { t } = useTranslation()
  const taskStoreTasks = useTaskStore((state) => state.tasks)
  const selectedTaskId = useTaskStore((state) => state.selectedTaskId)
  const planTasks = usePlanStore((state) => state.tasks)
  const viewMode = usePlanStore((state) => state.viewMode)
  const isApprovedPlan = viewMode === 'approved'
  const { job } = useActiveExecutionJob()
  const skeleton = job?.workflowSkeleton ?? null
  const phaseStates = job?.phaseStates

  // Data source switch: a domain pipeline skeleton takes precedence and turns
  // the canvas into the phase-level DAG; without one the canvas keeps the
  // legacy task-tree / approved-plan rendering (fixed_pipeline, history).
  const phaseTasks = useMemo(() => buildPhaseTasks(skeleton, phaseStates), [skeleton, phaseStates])
  const rawTasks = isApprovedPlan && planTasks.length > 0 ? planTasks : taskStoreTasks
  // display_subtasks expansion only applies to the legacy task-tree path;
  // skeleton phases are already the real execution steps.
  const tasks = useMemo<PhaseFlowTask[]>(
    () => phaseTasks ?? expandTasks(rawTasks),
    [phaseTasks, rawTasks]
  )

  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  const layoutNodes = useMemo(() => {
    const levels: Record<string, number> = {}
    const inDegree: Record<string, number> = {}

    tasks.forEach((task) => {
      inDegree[task.id] = task.dependencies.length
      levels[task.id] = 0
    })

    const queue = tasks.filter((t) => inDegree[t.id] === 0).map((t) => t.id)
    while (queue.length > 0) {
      const current = queue.shift()!
      const currentLevel = levels[current]
      const children = tasks.filter((t) => t.dependencies.includes(current))
      children.forEach((child) => {
        levels[child.id] = Math.max(levels[child.id], currentLevel + 1)
        inDegree[child.id]--
        if (inDegree[child.id] === 0) queue.push(child.id)
      })
    }

    const levelTasks: Record<number, string[]> = {}
    tasks.forEach((task) => {
      const level = levels[task.id] || 0
      levelTasks[level] = levelTasks[level] || []
      levelTasks[level].push(task.id)
    })

    const positions: Record<string, { x: number; y: number }> = {}
    const xGap = 280
    const yGap = 160

    Object.entries(levelTasks).forEach(([level, ids]) => {
      const y = 80 + parseInt(level) * yGap
      const totalWidth = (ids.length - 1) * xGap
      ids.forEach((id, index) => {
        positions[id] = { x: 100 + index * xGap - totalWidth / 2, y }
      })
    })

    return positions
  }, [tasks])

  useEffect(() => {
    const newNodes = tasks.map((task) => ({
      id: task.id,
      type: 'task',
      position: layoutNodes[task.id] || { x: 100, y: 100 },
      data: task,
      selected: (task.fromPhase || !isApprovedPlan) && task.id === selectedTaskId,
    }))

    const newEdges = tasks.flatMap((task) =>
      task.dependencies.map((depId) => ({
        id: `e-${depId}-${task.id}`,
        source: depId,
        target: task.id,
        animated: task.status === 'running',
        style: { stroke: task.status === 'running' ? '#2563eb' : '#cbd5e1', strokeWidth: 2 },
      }))
    )

    setNodes(newNodes)
    setEdges(newEdges)
  }, [tasks, selectedTaskId, isApprovedPlan, layoutNodes, setNodes, setEdges])

  return (
    <div className="relative h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.2}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="hsl(var(--muted-foreground))" gap={20} size={1} />
        <Controls className="!bg-card !text-foreground !border-border" />
        <MiniMap
          nodeStrokeWidth={3}
          className="!bg-card !border-border"
          maskColor="hsl(var(--background) / 0.7)"
        />
      </ReactFlow>

      {skeleton && (
        <div className="absolute left-3 top-3 z-10 rounded-md border border-border bg-card/90 px-2.5 py-1 text-xs font-medium text-muted-foreground shadow-sm backdrop-blur-sm">
          {t('workflow.domainLabel', { domain: skeleton.domain })}
        </div>
      )}

      {tasks.length === 0 && (
        <div className="absolute inset-0 z-10 flex items-center justify-center p-6">
          <div data-testid="workflow-empty" className="max-w-sm rounded-lg border border-border bg-card/95 p-6 text-center shadow-sm">
            <Workflow className="mx-auto h-8 w-8 text-muted-foreground" />
            <p className="mt-3 text-sm font-medium text-foreground">{t('workflow.emptyTitle')}</p>
            <p className="mt-1.5 text-xs text-muted-foreground">{t('workflow.emptyDesc')}</p>
          </div>
        </div>
      )}
    </div>
  )
}
