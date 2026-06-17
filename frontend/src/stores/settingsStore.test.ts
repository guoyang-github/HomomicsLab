import { describe, it, expect, beforeEach } from 'vitest'
import { useSettingsStore } from './settingsStore'

describe('settingsStore', () => {
  beforeEach(() => {
    useSettingsStore.setState(useSettingsStore.getInitialState())
  })

  it('should initialize with defaults', () => {
    const state = useSettingsStore.getState()
    expect(state.model.provider).toBe('openai')
    expect(state.model.model).toBe('gpt-4o')
    expect(state.execution.sandboxBackend).toBe('subprocess')
    expect(state.search.topK).toBe(5)
    expect(state.budget.monthlyBudget).toBe(50)
    expect(state.dataRetentionDays).toBe(0)
    expect(state.enableNotifications).toBe(true)
  })

  it('should update model config', () => {
    useSettingsStore.getState().updateModel({ model: 'gpt-4o-mini', temperature: 0.5 })
    const state = useSettingsStore.getState()
    expect(state.model.model).toBe('gpt-4o-mini')
    expect(state.model.temperature).toBe(0.5)
    expect(state.model.provider).toBe('openai')
  })

  it('should update execution config', () => {
    useSettingsStore.getState().updateExecution({ sandboxBackend: 'docker', timeoutSeconds: 600 })
    const state = useSettingsStore.getState()
    expect(state.execution.sandboxBackend).toBe('docker')
    expect(state.execution.timeoutSeconds).toBe(600)
  })

  it('should update search config', () => {
    useSettingsStore.getState().updateSearch({ topK: 10, similarityThreshold: 0.9 })
    const state = useSettingsStore.getState()
    expect(state.search.topK).toBe(10)
    expect(state.search.similarityThreshold).toBe(0.9)
  })

  it('should update budget config', () => {
    useSettingsStore.getState().updateBudget({ monthlyBudget: 100, perRequestBudget: 2 })
    const state = useSettingsStore.getState()
    expect(state.budget.monthlyBudget).toBe(100)
    expect(state.budget.perRequestBudget).toBe(2)
  })

  it('should toggle booleans and set retention', () => {
    useSettingsStore.getState().setAutoApprovePlans(true)
    useSettingsStore.getState().setEnableNotifications(false)
    useSettingsStore.getState().setDataRetentionDays(90)
    const state = useSettingsStore.getState()
    expect(state.autoApprovePlans).toBe(true)
    expect(state.enableNotifications).toBe(false)
    expect(state.dataRetentionDays).toBe(90)
  })

  it('should reset to defaults', () => {
    useSettingsStore.getState().updateModel({ model: 'custom-model' })
    useSettingsStore.getState().setDataRetentionDays(7)
    useSettingsStore.getState().reset()
    const state = useSettingsStore.getState()
    expect(state.model.model).toBe('gpt-4o')
    expect(state.dataRetentionDays).toBe(0)
  })
})
