import { describe, it, expect, beforeEach } from 'vitest'
import { usePlanStore } from './planStore'
import type { PlanRequestContent } from '@/types/chat'

function makePlan(): PlanRequestContent {
  return {
    plan_id: 'plan_1',
    response_text: 'test plan',
    plan: {
      plan_id: 'plan_1',
      status: 'pending_approval',
      is_fallback: false,
      intent_analysis_type: 'single_cell',
      phases: [
        {
          phase_type: 'qc',
          description: 'Quality control',
          required: true,
          skill_id: 'single_cell_qc',
          readonly: false,
          parameters: { min_genes: 200 },
        },
        {
          phase_type: 'normalization',
          description: 'Normalize data',
          required: true,
          skill_id: 'single_cell_norm',
          readonly: false,
          parameters: {},
        },
      ],
      version: 1,
    },
  }
}

describe('planStore', () => {
  beforeEach(() => {
    usePlanStore.getState().discardDraft()
  })

  it('loads a plan and derives tasks', () => {
    usePlanStore.getState().loadPlan(makePlan())
    const state = usePlanStore.getState()
    expect(state.draftPlan).not.toBeNull()
    expect(state.tasks).toHaveLength(2)
    expect(state.tasks[0].id).toBe('qc')
    expect(state.tasks[1].dependencies).toContain('qc')
  })

  it('adds a new phase after selected anchor', () => {
    usePlanStore.getState().loadPlan(makePlan())
    usePlanStore.getState().addPhase('clustering', { after: 'normalization' })
    const state = usePlanStore.getState()
    expect(state.tasks).toHaveLength(3)
    expect(state.tasks[2].id).toBe('clustering')
    expect(state.tasks[2].dependencies).toContain('normalization')
    expect(state.isDirty).toBe(true)
  })

  it('removes a phase and cleans dependencies', () => {
    usePlanStore.getState().loadPlan(makePlan())
    usePlanStore.getState().removePhase('qc')
    const state = usePlanStore.getState()
    expect(state.tasks).toHaveLength(1)
    expect(state.tasks[0].dependencies).toHaveLength(0)
    expect(state.isDirty).toBe(true)
  })

  it('updates dependencies for a phase', () => {
    usePlanStore.getState().loadPlan(makePlan())
    usePlanStore.getState().updateDependency('normalization', [])
    const state = usePlanStore.getState()
    expect(state.tasks.find((t) => t.id === 'normalization')?.dependencies).toHaveLength(0)
    expect(state.isDirty).toBe(true)
  })

  it('updates parameters', () => {
    usePlanStore.getState().loadPlan(makePlan())
    usePlanStore.getState().updateParameter('qc', 'min_genes', 300)
    const phase = usePlanStore.getState().draftPlan?.plan.phases.find((p) => p.phase_type === 'qc')
    expect(phase?.parameters?.min_genes).toBe(300)
  })

  it('computes modifications', () => {
    usePlanStore.getState().loadPlan(makePlan())
    usePlanStore.getState().updateParameter('qc', 'min_genes', 300)
    const modifications = usePlanStore.getState().getModifications()
    const paramMod = modifications.find((m) => m.action === 'update' && m.parameter === 'min_genes')
    expect(paramMod).toBeDefined()
    expect(paramMod?.old_value).toBe(200)
    expect(paramMod?.new_value).toBe(300)
  })

  it('resets dirty state after discard', () => {
    usePlanStore.getState().loadPlan(makePlan())
    usePlanStore.getState().addPhase('clustering')
    expect(usePlanStore.getState().isDirty).toBe(true)
    usePlanStore.getState().discardDraft()
    expect(usePlanStore.getState().draftPlan).toBeNull()
    expect(usePlanStore.getState().isDirty).toBe(false)
  })
})
