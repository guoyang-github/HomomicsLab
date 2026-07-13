import { useEffect, useMemo, useState } from 'react'
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
  type Node,
  type Edge,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { Database, FileOutput, Settings2 } from 'lucide-react'
import { lineageApi } from '@/services/api'
import { useProjectStore } from '@/stores/projectStore'
import { EmptyState } from '@/components/ui'
import { useTranslation } from '@/i18n'
import type { LineageNode, LineageEdge } from '@/types/api'

const typeConfig: Record<
  string,
  { label: string; color: string; bg: string; border: string; icon: React.ElementType }
> = {
  raw: {
    label: 'Raw',
    color: 'text-emerald-600 dark:text-emerald-400',
    bg: 'bg-emerald-50 dark:bg-emerald-950',
    border: 'border-emerald-300 dark:border-emerald-700',
    icon: Database,
  },
  data: {
    label: 'Raw',
    color: 'text-emerald-600 dark:text-emerald-400',
    bg: 'bg-emerald-50 dark:bg-emerald-950',
    border: 'border-emerald-300 dark:border-emerald-700',
    icon: Database,
  },
  intermediate: {
    label: 'Intermediate',
    color: 'text-blue-600 dark:text-blue-400',
    bg: 'bg-blue-50 dark:bg-blue-950',
    border: 'border-blue-300 dark:border-blue-700',
    icon: Settings2,
  },
  output: {
    label: 'Output',
    color: 'text-violet-600 dark:text-violet-400',
    bg: 'bg-violet-50 dark:bg-violet-950',
    border: 'border-violet-300 dark:border-violet-700',
    icon: FileOutput,
  },
}

function LineageNodeComponent({ data, selected }: NodeProps<LineageNode>) {
  const config = typeConfig[data.type] || typeConfig.raw
  const Icon = config.icon
  const fileName = data.path.split('/').pop() || data.path

  return (
    <div
      className={clsx(
        'relative min-w-[180px] max-w-[260px] rounded-xl border-2 bg-card p-3 shadow-card transition-all',
        selected ? 'ring-2 ring-primary ring-offset-2' : '',
        config.border
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-border" />

      <div className="flex items-start gap-2">
        <div className={clsx('rounded-full p-1.5', config.bg)}>
          <Icon className={clsx('h-4 w-4', config.color)} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-foreground truncate" title={fileName}>
            {fileName}
          </div>
          <div className={clsx('mt-0.5 text-[10px] font-medium', config.color)}>
            {config.label}
          </div>
        </div>
      </div>

      <div className="mt-2 text-[10px] text-muted-foreground truncate" title={data.created_by_task}>
        {data.created_by_task}
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-border" />
    </div>
  )
}

const nodeTypes = {
  lineage: LineageNodeComponent,
}

function computeLayout(nodes: LineageNode[], edges: LineageEdge[]) {
  const children: Record<string, string[]> = {}
  const inDegree: Record<string, number> = {}

  nodes.forEach((node) => {
    children[node.node_id] = []
    inDegree[node.node_id] = 0
  })

  edges.forEach((edge) => {
    children[edge.from_node]?.push(edge.to_node)
    inDegree[edge.to_node] = (inDegree[edge.to_node] || 0) + 1
  })

  const levels: Record<string, number> = {}
  const queue = nodes.filter((n) => (inDegree[n.node_id] || 0) === 0).map((n) => n.node_id)
  queue.forEach((id) => {
    levels[id] = 0
  })

  while (queue.length > 0) {
    const current = queue.shift()!
    const currentLevel = levels[current]
    children[current].forEach((childId) => {
      levels[childId] = Math.max(levels[childId] ?? 0, currentLevel + 1)
      inDegree[childId]--
      if (inDegree[childId] === 0) {
        queue.push(childId)
      }
    })
  }

  const levelNodes: Record<number, string[]> = {}
  nodes.forEach((node) => {
    const level = levels[node.node_id] || 0
    levelNodes[level] = levelNodes[level] || []
    levelNodes[level].push(node.node_id)
  })

  const positions: Record<string, { x: number; y: number }> = {}
  const xGap = 260
  const yGap = 140

  Object.entries(levelNodes).forEach(([level, ids]) => {
    const y = 60 + parseInt(level) * yGap
    const totalWidth = (ids.length - 1) * xGap
    ids.forEach((id, index) => {
      positions[id] = { x: 100 + index * xGap - totalWidth / 2, y }
    })
  })

  return positions
}

export function ProvenanceGraph() {
  const { t } = useTranslation()
  const currentProjectId = useProjectStore((state) => state.currentProjectId)
  const [lineage, setLineage] = useState<{ nodes: LineageNode[]; edges: LineageEdge[] } | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  useEffect(() => {
    if (!currentProjectId) {
      setLineage(null)
      setNodes([])
      setEdges([])
      return
    }

    setLoading(true)
    setError(null)
    lineageApi
      .getProjectLineage(currentProjectId)
      .then((res) => setLineage(res.data))
      .catch((err: any) => setError(err?.response?.data?.detail || 'Failed to load lineage'))
      .finally(() => setLoading(false))
  }, [currentProjectId])

  const positions = useMemo(() => {
    if (!lineage) return {}
    return computeLayout(lineage.nodes, lineage.edges)
  }, [lineage])

  useEffect(() => {
    if (!lineage) {
      setNodes([])
      setEdges([])
      return
    }

    const flowNodes: Node<LineageNode>[] = lineage.nodes.map((node) => ({
      id: node.node_id,
      type: 'lineage',
      position: positions[node.node_id] || { x: 100, y: 100 },
      data: node,
    }))

    const flowEdges: Edge[] = lineage.edges.map((edge) => ({
      id: `e-${edge.from_node}-${edge.to_node}`,
      source: edge.from_node,
      target: edge.to_node,
      label: edge.transform_type,
      style: { stroke: '#94a3b8', strokeWidth: 2 },
    }))

    setNodes(flowNodes)
    setEdges(flowEdges)
  }, [lineage, positions, setNodes, setEdges])

  if (!currentProjectId) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <EmptyState
          title={t('workspace.noProjectSelected')}
          description={t('workspace.noProjectSelectedDesc')}
        />
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        {t('workspace.loadingProvenance')}
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center text-error">
        {error}
      </div>
    )
  }

  if (!lineage || lineage.nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <EmptyState
          title={t('workspace.noProvenanceData')}
          description={t('workspace.noProvenanceDataDesc')}
        />
      </div>
    )
  }

  return (
    <div className="h-full w-full">
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
    </div>
  )
}
