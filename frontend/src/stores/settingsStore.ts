import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type LlmProvider = 'openai' | 'anthropic' | 'azure' | 'local' | 'custom'
export type SandboxBackend = 'subprocess' | 'docker' | 'local'

export interface ModelConfig {
  provider: LlmProvider
  model: string
  apiKey: string
  baseUrl: string
  temperature: number
  maxTokens: number
}

export interface ExecutionConfig {
  sandboxBackend: SandboxBackend
  workDir: string
  dataDir: string
  timeoutSeconds: number
  memoryLimitMb: number
}

export interface SearchConfig {
  embeddingModel: string
  topK: number
  similarityThreshold: number
}

export interface BudgetConfig {
  perRequestBudget: number
  monthlyBudget: number
  approvalThresholdTokens: number
  approvalThresholdCost: number
}

export interface SettingsState {
  model: ModelConfig
  execution: ExecutionConfig
  search: SearchConfig
  budget: BudgetConfig
  dataRetentionDays: number
  autoApprovePlans: boolean
  enableNotifications: boolean
  updateModel: (config: Partial<ModelConfig>) => void
  updateExecution: (config: Partial<ExecutionConfig>) => void
  updateSearch: (config: Partial<SearchConfig>) => void
  updateBudget: (config: Partial<BudgetConfig>) => void
  setDataRetentionDays: (days: number) => void
  setAutoApprovePlans: (value: boolean) => void
  setEnableNotifications: (value: boolean) => void
  reset: () => void
}

const defaultModel: ModelConfig = {
  provider: 'openai',
  model: 'gpt-4o',
  apiKey: '',
  baseUrl: '',
  temperature: 0.2,
  maxTokens: 4096,
}

const defaultExecution: ExecutionConfig = {
  sandboxBackend: 'subprocess',
  workDir: './workdir',
  dataDir: './data',
  timeoutSeconds: 300,
  memoryLimitMb: 4096,
}

const defaultSearch: SearchConfig = {
  embeddingModel: 'text-embedding-3-small',
  topK: 5,
  similarityThreshold: 0.75,
}

const defaultBudget: BudgetConfig = {
  perRequestBudget: 1.0,
  monthlyBudget: 50.0,
  approvalThresholdTokens: 100000,
  approvalThresholdCost: 5.0,
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      model: defaultModel,
      execution: defaultExecution,
      search: defaultSearch,
      budget: defaultBudget,
      dataRetentionDays: 30,
      autoApprovePlans: false,
      enableNotifications: true,
      updateModel: (config) => set((state) => ({ model: { ...state.model, ...config } })),
      updateExecution: (config) => set((state) => ({ execution: { ...state.execution, ...config } })),
      updateSearch: (config) => set((state) => ({ search: { ...state.search, ...config } })),
      updateBudget: (config) => set((state) => ({ budget: { ...state.budget, ...config } })),
      setDataRetentionDays: (days) => set({ dataRetentionDays: days }),
      setAutoApprovePlans: (value) => set({ autoApprovePlans: value }),
      setEnableNotifications: (value) => set({ enableNotifications: value }),
      reset: () =>
        set({
          model: defaultModel,
          execution: defaultExecution,
          search: defaultSearch,
          budget: defaultBudget,
          dataRetentionDays: 30,
          autoApprovePlans: false,
          enableNotifications: true,
        }),
    }),
    {
      name: 'homomics-settings',
    }
  )
)
