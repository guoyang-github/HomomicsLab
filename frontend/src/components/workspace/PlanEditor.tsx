import { useEffect, useCallback, useMemo, useState, useRef } from 'react'
import { clsx } from 'clsx'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  type NodeProps,
  type Connection,
  type Edge,
  type NodeChange,
  type EdgeChange,
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  useReactFlow,
} from 'reactflow'
import 'reactflow/dist/style.css'
import {
  Save,
  Check,
  X,
  Trash2,
  Plus,
  Layers,
  Wrench,
  Settings,
  AlertCircle,
} from 'lucide-react'
import { usePlanStore } from '@/stores/planStore'
import { planApi } from '@/services/api'
import { useChatStore } from '@/stores/chatStore'
import { useTaskStore } from '@/stores/taskStore'
import { useTranslation } from '@/i18n'
import { Button, Badge, Input, Select } from '@/components/ui'
import { toastError, toastSuccess } from '@/stores/toastStore'
import type { TaskNode } from '@/types/tasks'

const paletteItems = [
  { phase_type: 'qc', labelKey: 'planEditor.palette.qc.label', descKey: 'planEditor.palette.qc.desc' },
  { phase_type: 'normalization', labelKey: 'planEditor.palette.normalization.label', descKey: 'planEditor.palette.normalization.desc' },
  { phase_type: 'dim_reduction', labelKey: 'planEditor.palette.dimReduction.label', descKey: 'planEditor.palette.dimReduction.desc' },
  { phase_type: 'clustering', labelKey: 'planEditor.palette.clustering.label', descKey: 'planEditor.palette.clustering.desc' },
  { phase_type: 'annotation', labelKey: 'planEditor.palette.annotation.label', descKey: 'planEditor.palette.annotation.desc' },
  { phase_type: 'differential_expression', labelKey: 'planEditor.palette.differentialExpression.label', descKey: 'planEditor.palette.differentialExpression.desc' },
  { phase_type: 'pathway', labelKey: 'planEditor.palette.pathway.label', descKey: 'planEditor.palette.pathway.desc' },
]

function PlanNodeComponent({ data, selected }: NodeProps<TaskNode>) {
  const { t } = useTranslation()
  const removePhase = usePlanStore((state) => state.removePhase)
  const selectTask = usePlanStore((state) => state.selectTask)

  return (
    <div
      onClick={() => selectTask(data.id)}
      className={clsx(
        'relative min-w-[180px] max-w-[260px] cursor-pointer rounded-xl border-2 bg-card p-4 shadow-card transition-all',
        selected ? 'ring-2 ring-primary ring-offset-2' : '',
        'border-border hover:border-primary/50'
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-border" />
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="text-sm font-semibold text-foreground">{data.name}</div>
          <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">{data.description}</div>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation()
            removePhase(data.id)
          }}
          className="rounded p-1 text-muted-foreground hover:bg-error/10 hover:text-error"
          title={t('planEditor.deletePhase')}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-1">
        {data.skills_required.length > 0 ? (
          data.skills_required.map((skill) => (
            <Badge key={skill} variant="outline" size="sm">
              {skill}
            </Badge>
          ))
        ) : (
          <Badge variant="secondary" size="sm">{t('planEditor.noSkillBound')}</Badge>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-border" />
    </div>
  )
}

const nodeTypes = { plan: PlanNodeComponent }

export function PlanEditor() {
  const { t } = useTranslation()
  const draftPlan = usePlanStore((state) => state.draftPlan)
  const tasks = usePlanStore((state) => state.tasks)
  const positions = usePlanStore((state) => state.positions)
  const selectedTaskId = usePlanStore((state) => state.selectedTaskId)
  const isDirty = usePlanStore((state) => state.isDirty)
  const isSaving = usePlanStore((state) => state.isSaving)
  const selectTask = usePlanStore((state) => state.selectTask)
  const updateNodePosition = usePlanStore((state) => state.updateNodePosition)
  const removePhase = usePlanStore((state) => state.removePhase)
  const updateDependency = usePlanStore((state) => state.updateDependency)
  const addPhase = usePlanStore((state) => state.addPhase)
  const setSaving = usePlanStore((state) => state.setSaving)
  const markClean = usePlanStore((state) => state.markClean)
  const updateAfterSave = usePlanStore((state) => state.updateAfterSave)
  const discardDraft = usePlanStore((state) => state.discardDraft)
  const getModifications = usePlanStore((state) => state.getModifications)

  const addMessage = useChatStore((state) => state.addMessage)
  const setTaskTree = useTaskStore((state) => state.setTaskTree)

  const [nodes, setNodes] = useState(applyNodeChanges([], []))
  const [edges, setEdges] = useState(applyEdgeChanges([], []))
  const { screenToFlowPosition } = useReactFlow()

  const initialSyncRef = useRef<string | null>(null)

  const derivedEdges = useMemo<Edge[]>(() => {
    return tasks.flatMap((task) =>
      task.dependencies.map((depId) => ({
        id: `e-${depId}-${task.id}`,
        source: depId,
        target: task.id,
        type: 'smoothstep' as const,
        style: { stroke: '#94a3b8', strokeWidth: 2 },
      }))
    )
  }, [tasks])

  useEffect(() => {
    const newNodes = tasks.map((task) => ({
      id: task.id,
      type: 'plan',
      position: positions[task.id] || { x: 0, y: 0 },
      data: task,
      selected: task.id === selectedTaskId,
    }))
    setNodes(newNodes)
  }, [tasks, positions, selectedTaskId])

  useEffect(() => {
    setEdges(derivedEdges)
  }, [derivedEdges])

  useEffect(() => {
    if (draftPlan && tasks.length > 0 && initialSyncRef.current !== draftPlan.plan_id) {
      initialSyncRef.current = draftPlan.plan_id
      setTaskTree(tasks)
    }
  }, [draftPlan, tasks, setTaskTree])

  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => {
      const positionChanges: { id: string; position: { x: number; y: number } }[] = []
      const removeIds: string[] = []
      const selectIds: string[] = []
      const deselectIds: string[] = []

      changes.forEach((change) => {
        if (change.type === 'position' && change.position && change.id) {
          positionChanges.push({ id: change.id, position: change.position })
        }
        if (change.type === 'remove' && change.id) {
          removeIds.push(change.id)
        }
        if (change.type === 'select' && change.id) {
          if (change.selected) selectIds.push(change.id)
          else deselectIds.push(change.id)
        }
      })

      positionChanges.forEach(({ id, position }) => updateNodePosition(id, position))
      removeIds.forEach((id) => removePhase(id))
      if (selectIds.length === 1) {
        selectTask(selectIds[0])
      } else if (deselectIds.includes(selectedTaskId || '')) {
        selectTask(null)
      }

      setNodes((nds) => applyNodeChanges(changes, nds))
    },
    [removePhase, selectedTaskId, selectTask, updateNodePosition]
  )

  const handleEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      const removed = changes.filter((c) => c.type === 'remove')
      removed.forEach((change) => {
        const edgeId = (change as EdgeChange & { id: string }).id
        const match = edgeId.match(/^e-(.+)-(.+)$/)
        if (match) {
          const [, source, target] = match
          const task = tasks.find((t) => t.id === target)
          if (task) {
            updateDependency(target, task.dependencies.filter((d) => d !== source))
          }
        }
      })
      setEdges((eds) => applyEdgeChanges(changes, eds))
    },
    [tasks, updateDependency]
  )

  const handleConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target || connection.source === connection.target) return
      const targetTask = tasks.find((t) => t.id === connection.target)
      if (!targetTask) return
      if (targetTask.dependencies.includes(connection.source)) return
      updateDependency(connection.target, [...targetTask.dependencies, connection.source])
      setEdges((eds) => addEdge({ ...connection, type: 'smoothstep', style: { stroke: '#94a3b8', strokeWidth: 2 } }, eds))
    },
    [tasks, updateDependency]
  )

  const onDragStart = (event: React.DragEvent<HTMLDivElement>, phaseType: string) => {
    event.dataTransfer.setData('application/reactflow-plan-phase', phaseType)
    event.dataTransfer.effectAllowed = 'move'
  }

  const onDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    const phaseType = event.dataTransfer.getData('application/reactflow-plan-phase')
    if (!phaseType) return
    const position = screenToFlowPosition({ x: event.clientX, y: event.clientY })
    const nearest = tasks.reduce<{ id: string; distance: number } | null>((best, task) => {
      const pos = positions[task.id] || { x: 0, y: 0 }
      const distance = Math.hypot(pos.x - position.x, pos.y - position.y)
      if (!best || distance < best.distance) return { id: task.id, distance }
      return best
    }, null)
    addPhase(phaseType, { after: nearest?.id })
  }

  const onDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }

  const submitPlan = async (approved: boolean) => {
    if (!draftPlan) return
    setSaving(true)
    try {
      const modifications = getModifications()
      const response = await planApi.modify(draftPlan.plan_id, approved, modifications)
      const actionText = approved ? t('planEditor.approveExecute') : t('planEditor.saveDraft')
      toastSuccess(t('planEditor.submitSuccess', { action: actionText }))
      addMessage({
        id: `msg_${Date.now()}`,
        type: 'system',
        content: t('planEditor.submitMessage', { action: actionText, status: response.data.status }),
        sender: 'system',
        timestamp: new Date().toISOString(),
      })
      if (approved) {
        discardDraft()
        if (response.data.job_id) {
          addMessage({
            id: `msg_${Date.now()}_job`,
            type: 'system',
            content: t('planEditor.jobCreated', { jobId: response.data.job_id.slice(0, 8) }),
            sender: 'system',
            timestamp: new Date().toISOString(),
          })
        }
      } else {
        updateAfterSave(response.data.plan_id)
        markClean()
      }
    } catch (error: any) {
      toastError(error?.response?.data?.detail || t('planEditor.submitFailed'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex h-full w-full">
      <div className="w-56 shrink-0 border-r border-border bg-card p-3">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
          <Layers className="h-4 w-4" />
          {t('planEditor.paletteTitle')}
        </div>
        <div className="space-y-2">
          {paletteItems.map((item) => (
            <div
              key={item.phase_type}
              draggable
              onDragStart={(e) => onDragStart(e, item.phase_type)}
              className="cursor-move rounded-lg border border-border bg-background p-2 transition-colors hover:border-primary/50 hover:bg-primary/5"
            >
              <div className="text-xs font-medium text-foreground">{t(item.labelKey)}</div>
              <div className="text-[10px] text-muted-foreground">{t(item.descKey)}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center justify-between border-b border-border bg-card px-4 py-2">
          <div className="flex items-center gap-2">
            <Badge variant="outline" size="sm">Plan Editor</Badge>
            {draftPlan && (
              <span className="text-xs text-muted-foreground">
                {t('planEditor.planInfo', { count: draftPlan.plan.phases.length, version: draftPlan.plan.version })}
              </span>
            )}
            {isDirty && (
              <Badge variant="warning" size="sm">{t('planEditor.modified')}</Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => discardDraft()} disabled={isSaving}>
              <X className="mr-1 h-3.5 w-3.5" />
              {t('planEditor.discard')}
            </Button>
            <Button variant="secondary" size="sm" onClick={() => submitPlan(false)} loading={isSaving} disabled={!isDirty}>
              <Save className="mr-1 h-3.5 w-3.5" />
              {t('planEditor.saveDraft')}
            </Button>
            <Button size="sm" onClick={() => submitPlan(true)} loading={isSaving}>
              <Check className="mr-1 h-3.5 w-3.5" />
              {t('planEditor.approveExecute')}
            </Button>
          </div>
        </div>

        <div className="relative flex-1 overflow-hidden" onDrop={onDrop} onDragOver={onDragOver}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={handleNodesChange}
            onEdgesChange={handleEdgesChange}
            onConnect={handleConnect}
            nodeTypes={nodeTypes}
            fitView
            minZoom={0.2}
            maxZoom={2}
            deleteKeyCode={['Backspace', 'Delete']}
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
      </div>

      <ParameterPanel />
    </div>
  )
}

function ParameterPanel() {
  const { t } = useTranslation()
  const selectedTaskId = usePlanStore((state) => state.selectedTaskId)
  const tasks = usePlanStore((state) => state.tasks)
  const updateParameter = usePlanStore((state) => state.updateParameter)
  const updatePhaseField = usePlanStore((state) => state.updatePhaseField)
  const draftPlan = usePlanStore((state) => state.draftPlan)

  const phase = useMemo(() => {
    if (!draftPlan || !selectedTaskId) return null
    return draftPlan.plan.phases.find((p) => p.phase_type === selectedTaskId) || null
  }, [draftPlan, selectedTaskId])

  const [newParamKey, setNewParamKey] = useState('')
  const [newParamValue, setNewParamValue] = useState('')

  if (!phase) {
    return (
      <div className="w-72 shrink-0 border-l border-border bg-card p-4">
        <div className="rounded-lg border border-border bg-muted/50 p-4 text-center">
          <Settings className="mx-auto mb-2 h-5 w-5 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{t('planEditor.selectNodeHint')}</p>
        </div>
      </div>
    )
  }

  const task = tasks.find((t) => t.id === selectedTaskId)
  const params = phase.parameters || {}

  return (
    <div className="w-72 shrink-0 overflow-y-auto border-l border-border bg-card p-4">
      <div className="mb-4 flex items-center gap-2">
        <Wrench className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold text-foreground">{phase.phase_type}</h3>
      </div>

      <div className="mb-4 space-y-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-muted-foreground">{t('planEditor.description')}</label>
          <TextareaAuto
            value={phase.description || ''}
            onChange={(value) => updatePhaseField(phase.phase_type, 'description', value)}
            rows={2}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-muted-foreground">{t('planEditor.skillId')}</label>
          <Input
            value={phase.skill_id || ''}
            onChange={(e) => updatePhaseField(phase.phase_type, 'skill_id', e.target.value || undefined)}
            placeholder="single_cell_qc"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-muted-foreground">{t('planEditor.required')}</label>
          <Select
            value={phase.required === false ? 'false' : 'true'}
            options={[
              { value: 'true', label: t('planEditor.requiredLabel') },
              { value: 'false', label: t('planEditor.optional') },
            ]}
            onChange={(e) => updatePhaseField(phase.phase_type, 'required', e.target.value === 'true')}
          />
        </div>
      </div>

      <div className="mb-2 text-xs font-medium text-muted-foreground">{t('planEditor.dependencies')}</div>
      {task && task.dependencies.length > 0 ? (
        <div className="mb-4 flex flex-wrap gap-1">
          {task.dependencies.map((dep) => (
            <Badge key={dep} variant="outline" size="sm">{dep}</Badge>
          ))}
        </div>
      ) : (
        <div className="mb-4 text-xs text-muted-foreground">{t('planEditor.noDependencies')}</div>
      )}

      <div className="mb-2 text-xs font-medium text-muted-foreground">{t('planEditor.parameters')}</div>
      <div className="space-y-2">
        {Object.entries(params).map(([key, value]) => (
          <div key={key} className="flex items-center gap-2">
            <span className="w-20 truncate text-xs text-muted-foreground">{key}</span>
            <Input
              value={String(value ?? '')}
              onChange={(e) => updateParameter(phase.phase_type, key, parseValue(e.target.value, value))}
              className="flex-1"
            />
            <button
              onClick={() => {
                const next = { ...params }
                delete next[key]
                updatePhaseField(phase.phase_type, 'parameters', next)
              }}
              className="rounded p-1 text-muted-foreground hover:text-error"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>

      <div className="mt-4 space-y-2 rounded-lg border border-border bg-muted/30 p-3">
        <div className="text-xs font-medium text-muted-foreground">{t('planEditor.addParameter')}</div>
        <Input
          value={newParamKey}
          onChange={(e) => setNewParamKey(e.target.value)}
          placeholder={t('planEditor.paramName')}
          className="h-8 text-xs"
        />
        <Input
          value={newParamValue}
          onChange={(e) => setNewParamValue(e.target.value)}
          placeholder={t('planEditor.paramValue')}
          className="h-8 text-xs"
        />
        <Button
          size="sm"
          variant="outline"
          className="w-full"
          onClick={() => {
            if (!newParamKey.trim()) return
            updateParameter(phase.phase_type, newParamKey, parseValue(newParamValue, ''))
            setNewParamKey('')
            setNewParamValue('')
          }}
        >
          <Plus className="mr-1 h-3.5 w-3.5" />
          {t('planEditor.add')}
        </Button>
      </div>

      {phase.readonly && (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-warning/20 bg-warning/10 p-3 text-xs text-warning-foreground">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5" />
          {t('planEditor.readonlyWarning')}
        </div>
      )}
    </div>
  )
}

function TextareaAuto({ value, onChange, rows = 2 }: { value: string; onChange: (value: string) => void; rows?: number }) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={rows}
      className={clsx(
        'w-full resize-none rounded-lg border border-border bg-card px-3 py-2 text-sm',
        'text-card-foreground placeholder:text-muted-foreground',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1'
      )}
    />
  )
}

function parseValue(raw: string, original: unknown): unknown {
  if (typeof original === 'number') {
    const num = Number(raw)
    return Number.isNaN(num) ? raw : num
  }
  if (original === true || original === false) {
    return raw === 'true'
  }
  if (raw === 'true') return true
  if (raw === 'false') return false
  if (raw === '') return ''
  const num = Number(raw)
  if (!Number.isNaN(num) && raw.trim() !== '') return num
  return raw
}
