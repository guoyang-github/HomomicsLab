import { create } from 'zustand'
import type { TaskNode } from '@/types/tasks'
import type { PlanRequestContent, PlanPhase } from '@/types/chat'

export interface PlanModification {
  phase_type: string
  action: 'update' | 'remove' | 'add' | 'update_dependency'
  parameter?: string
  old_value?: unknown
  new_value?: unknown
  after?: string
  before?: string
  description?: string
  required?: boolean
  skill_id?: string
  dependencies?: string[]
}

export interface PlanTransition {
  from: string
  to: string
  type: string
}

interface PlanDraftState {
  draftPlan: PlanRequestContent | null
  originalPhases: PlanPhase[]
  originalTransitions: PlanTransition[]
  transitions: PlanTransition[]
  tasks: TaskNode[]
  selectedTaskId: string | null
  isDirty: boolean
  isSaving: boolean
  positions: Record<string, { x: number; y: number }>
}

interface PlanState extends PlanDraftState {
  loadPlan: (content: PlanRequestContent) => void
  discardDraft: () => void
  selectTask: (taskId: string | null) => void
  setPositions: (positions: Record<string, { x: number; y: number }>) => void
  updateNodePosition: (taskId: string, position: { x: number; y: number }) => void
  addPhase: (phaseType: string, options?: { after?: string; skillId?: string; description?: string }) => void
  removePhase: (phaseType: string) => void
  updateDependency: (phaseType: string, dependencies: string[]) => void
  updateParameter: (phaseType: string, key: string, value: unknown) => void
  updatePhaseField: (phaseType: string, field: keyof PlanPhase, value: unknown) => void
  getModifications: () => PlanModification[]
  setSaving: (saving: boolean) => void
  markClean: () => void
  updateAfterSave: (planId: string) => void
}

const defaultDurationMinutes = 10

function buildTransitions(phases: PlanPhase[]): PlanTransition[] {
  const transitions: PlanTransition[] = []
  for (let i = 0; i < phases.length - 1; i++) {
    transitions.push({
      from: phases[i].phase_type,
      to: phases[i + 1].phase_type,
      type: 'followed_by',
    })
  }
  return transitions
}

function phaseToTask(phase: PlanPhase, transitions: PlanTransition[]): TaskNode {
  const deps = transitions
    .filter((t) => t.to === phase.phase_type && (t.type === 'followed_by' || t.type === 'depends_on'))
    .map((t) => t.from)
  return {
    id: phase.phase_type,
    name: phase.phase_type,
    description: phase.description || `${phase.phase_type} analysis step`,
    phase: phase.phase_type,
    status: 'pending',
    dependencies: deps,
    agent_assignment: undefined,
    skills_required: phase.skill_id ? [phase.skill_id] : [],
    estimated_duration_minutes: defaultDurationMinutes,
    parameters: phase.parameters ? { ...phase.parameters } : {},
  }
}

function tasksFromPhases(phases: PlanPhase[], transitions: PlanTransition[]): TaskNode[] {
  return phases.map((p) => phaseToTask(p, transitions))
}

function layoutPositions(
  tasks: TaskNode[],
  existing: Record<string, { x: number; y: number }> = {}
): Record<string, { x: number; y: number }> {
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
  const xGap = 260
  const yGap = 160

  Object.entries(levelTasks).forEach(([level, ids]) => {
    const y = 80 + parseInt(level) * yGap
    const totalWidth = (ids.length - 1) * xGap
    ids.forEach((id, index) => {
      positions[id] = existing[id] || { x: 100 + index * xGap - totalWidth / 2, y }
    })
  })

  return positions
}

function dependenciesFor(phaseType: string, transitions: PlanTransition[]): string[] {
  return transitions
    .filter((t) => t.to === phaseType && (t.type === 'followed_by' || t.type === 'depends_on'))
    .map((t) => t.from)
}

function replacePhaseInTransitions(
  transitions: PlanTransition[],
  oldPhase: string,
  newPhase?: string
): PlanTransition[] {
  return transitions
    .filter((t) => t.from !== oldPhase && t.to !== oldPhase)
    .map((t) => ({
      from: t.from === oldPhase ? (newPhase as string) : t.from,
      to: t.to === oldPhase ? (newPhase as string) : t.to,
      type: t.type,
    }))
}

export const usePlanStore = create<PlanState>((set, get) => ({
  draftPlan: null,
  originalPhases: [],
  originalTransitions: [],
  transitions: [],
  tasks: [],
  selectedTaskId: null,
  isDirty: false,
  isSaving: false,
  positions: {},

  loadPlan: (content) => {
    const phases = content.plan.phases.map((p) => ({ ...p }))
    const transitions = content.plan.transitions?.length
      ? content.plan.transitions.map((t) => ({ ...t }))
      : buildTransitions(phases)
    const tasks = tasksFromPhases(phases, transitions)
    set({
      draftPlan: content,
      originalPhases: content.plan.phases.map((p) => ({ ...p })),
      originalTransitions: transitions.map((t) => ({ ...t })),
      transitions,
      tasks,
      selectedTaskId: null,
      isDirty: false,
      isSaving: false,
      positions: layoutPositions(tasks),
    })
  },

  discardDraft: () =>
    set({
      draftPlan: null,
      originalPhases: [],
      originalTransitions: [],
      transitions: [],
      tasks: [],
      selectedTaskId: null,
      isDirty: false,
      isSaving: false,
      positions: {},
    }),

  selectTask: (taskId) => set({ selectedTaskId: taskId }),

  setPositions: (positions) => set({ positions }),

  updateNodePosition: (taskId, position) =>
    set((state) => ({
      positions: { ...state.positions, [taskId]: position },
    })),

  addPhase: (phaseType, options = {}) => {
    const { after, skillId, description } = options
    set((state) => {
      if (!state.draftPlan) return state
      if (state.tasks.some((t) => t.id === phaseType)) return state

      const newPhase: PlanPhase = {
        phase_type: phaseType,
        description: description || `${phaseType} analysis step`,
        required: true,
        skill_id: skillId,
        readonly: false,
        parameters: {},
      }

      const phases = [...state.draftPlan.plan.phases]
      let transitions = [...state.transitions]

      if (after && phases.some((p) => p.phase_type === after)) {
        const idx = phases.findIndex((p) => p.phase_type === after)
        phases.splice(idx + 1, 0, newPhase)
        const oldNextEdgeIndex = transitions.findIndex((t) => t.from === after && t.type === 'followed_by')
        if (oldNextEdgeIndex >= 0) {
          const oldNext = transitions[oldNextEdgeIndex].to
          transitions.splice(oldNextEdgeIndex, 1)
          transitions.push({ from: after, to: phaseType, type: 'followed_by' })
          transitions.push({ from: phaseType, to: oldNext, type: 'followed_by' })
        } else {
          transitions.push({ from: after, to: phaseType, type: 'followed_by' })
        }
      } else {
        phases.push(newPhase)
        const prev = phases[phases.length - 2]
        if (prev) {
          transitions.push({ from: prev.phase_type, to: phaseType, type: 'followed_by' })
        }
      }

      const newPlan: PlanRequestContent = {
        ...state.draftPlan,
        plan: {
          ...state.draftPlan.plan,
          phases,
        },
      }
      const tasks = tasksFromPhases(phases, transitions)
      return {
        draftPlan: newPlan,
        transitions,
        tasks,
        positions: layoutPositions(tasks, state.positions),
        isDirty: true,
      }
    })
  },

  removePhase: (phaseType) => {
    set((state) => {
      if (!state.draftPlan) return state
      const phases = state.draftPlan.plan.phases.filter((p) => p.phase_type !== phaseType)
      let transitions = replacePhaseInTransitions(state.transitions, phaseType)

      // Stitch predecessor to successor to keep chain
      const preds = dependenciesFor(phaseType, state.transitions)
      const succs = state.transitions
        .filter((t) => t.from === phaseType && (t.type === 'followed_by' || t.type === 'depends_on'))
        .map((t) => t.to)
      preds.forEach((pred) => {
        succs.forEach((succ) => {
          if (pred !== succ && !transitions.some((t) => t.from === pred && t.to === succ)) {
            transitions.push({ from: pred, to: succ, type: 'followed_by' })
          }
        })
      })

      const newPlan: PlanRequestContent = {
        ...state.draftPlan,
        plan: {
          ...state.draftPlan.plan,
          phases,
        },
      }
      const tasks = tasksFromPhases(phases, transitions)
      const positions = { ...state.positions }
      delete positions[phaseType]
      return {
        draftPlan: newPlan,
        transitions,
        tasks,
        positions: layoutPositions(tasks, positions),
        selectedTaskId: state.selectedTaskId === phaseType ? null : state.selectedTaskId,
        isDirty: true,
      }
    })
  },

  updateDependency: (phaseType, dependencies) => {
    set((state) => {
      if (!state.draftPlan) return state
      const phases = state.draftPlan.plan.phases
      let transitions = state.transitions.filter(
        (t) => !(t.to === phaseType && (t.type === 'followed_by' || t.type === 'depends_on'))
      )
      dependencies.forEach((dep) => {
        if (dep !== phaseType && phases.some((p) => p.phase_type === dep)) {
          transitions.push({ from: dep, to: phaseType, type: 'followed_by' })
        }
      })
      const newPlan: PlanRequestContent = {
        ...state.draftPlan,
        plan: {
          ...state.draftPlan.plan,
          phases: phases.map((p) => ({ ...p })),
        },
      }
      const tasks = tasksFromPhases(phases, transitions)
      return {
        draftPlan: newPlan,
        transitions,
        tasks,
        positions: layoutPositions(tasks, state.positions),
        isDirty: true,
      }
    })
  },

  updateParameter: (phaseType, key, value) => {
    set((state) => {
      if (!state.draftPlan) return state
      const phases = state.draftPlan.plan.phases.map((p) => {
        if (p.phase_type !== phaseType) return p
        return {
          ...p,
          parameters: {
            ...(p.parameters || {}),
            [key]: value,
          },
        }
      })
      const newPlan: PlanRequestContent = {
        ...state.draftPlan,
        plan: {
          ...state.draftPlan.plan,
          phases,
        },
      }
      const tasks = tasksFromPhases(phases, state.transitions)
      return {
        draftPlan: newPlan,
        tasks,
        isDirty: true,
      }
    })
  },

  updatePhaseField: (phaseType, field, value) => {
    set((state) => {
      if (!state.draftPlan) return state
      const phases = state.draftPlan.plan.phases.map((p) => {
        if (p.phase_type !== phaseType) return p
        return { ...p, [field]: value }
      })
      const newPlan: PlanRequestContent = {
        ...state.draftPlan,
        plan: {
          ...state.draftPlan.plan,
          phases,
        },
      }
      const tasks = tasksFromPhases(phases, state.transitions)
      return {
        draftPlan: newPlan,
        tasks,
        positions: layoutPositions(tasks, state.positions),
        isDirty: true,
      }
    })
  },

  getModifications: () => {
    const state = get()
    const modifications: PlanModification[] = []
    if (!state.draftPlan) return modifications

    const originalMap = new Map(state.originalPhases.map((p) => [p.phase_type, p]))
    const currentMap = new Map(state.draftPlan.plan.phases.map((p) => [p.phase_type, p]))

    // Removed phases
    for (const [phaseType] of originalMap) {
      if (!currentMap.has(phaseType)) {
        modifications.push({ phase_type: phaseType, action: 'remove' })
      }
    }

    // Added phases
    state.draftPlan.plan.phases.forEach((phase, index) => {
      if (!originalMap.has(phase.phase_type)) {
        const after = index > 0 ? state.draftPlan!.plan.phases[index - 1].phase_type : undefined
        const deps = dependenciesFor(phase.phase_type, state.transitions).filter((d) => d !== after)
        modifications.push({
          phase_type: phase.phase_type,
          action: 'add',
          after,
          description: phase.description,
          required: phase.required,
          skill_id: phase.skill_id,
          dependencies: deps.length > 0 ? deps : undefined,
        })
      }
    })

    // Updated phases
    for (const phase of state.draftPlan.plan.phases) {
      const original = originalMap.get(phase.phase_type)
      if (!original) continue

      if (phase.description !== original.description) {
        modifications.push({
          phase_type: phase.phase_type,
          action: 'update',
          parameter: 'description',
          old_value: original.description,
          new_value: phase.description,
        })
      }
      if (phase.skill_id !== original.skill_id) {
        modifications.push({
          phase_type: phase.phase_type,
          action: 'update',
          parameter: 'skill_id',
          old_value: original.skill_id,
          new_value: phase.skill_id,
        })
      }
      if (phase.required !== original.required) {
        modifications.push({
          phase_type: phase.phase_type,
          action: 'update',
          parameter: 'required',
          old_value: original.required,
          new_value: phase.required,
        })
      }

      const originalParams = original.parameters || {}
      const currentParams = phase.parameters || {}
      const allKeys = new Set([...Object.keys(originalParams), ...Object.keys(currentParams)])
      for (const key of allKeys) {
        if (originalParams[key] !== currentParams[key]) {
          modifications.push({
            phase_type: phase.phase_type,
            action: 'update',
            parameter: key,
            old_value: originalParams[key],
            new_value: currentParams[key],
          })
        }
      }

      // Dependency changes
      const originalDeps = dependenciesFor(phase.phase_type, state.originalTransitions).sort()
      const currentDeps = dependenciesFor(phase.phase_type, state.transitions).sort()
      if (JSON.stringify(originalDeps) !== JSON.stringify(currentDeps)) {
        modifications.push({
          phase_type: phase.phase_type,
          action: 'update_dependency',
          dependencies: currentDeps,
        })
      }
    }

    return modifications
  },

  setSaving: (isSaving) => set({ isSaving }),
  markClean: () => set({ isDirty: false }),

  updateAfterSave: (planId) => {
    set((state) => {
      if (!state.draftPlan) return state
      return {
        draftPlan: {
          ...state.draftPlan,
          plan_id: planId,
          plan: {
            ...state.draftPlan.plan,
            plan_id: planId,
          },
        },
        originalPhases: state.draftPlan.plan.phases.map((p) => ({ ...p })),
        originalTransitions: state.transitions.map((t) => ({ ...t })),
        isDirty: false,
      }
    })
  },
}))
