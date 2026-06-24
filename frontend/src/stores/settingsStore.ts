import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { settingsApi } from '@/services/api'

export type LlmProvider = 'openai' | 'anthropic' | 'azure' | 'moonshot' | 'deepseek' | 'qwen' | 'local' | 'custom'
export type SandboxBackend = 'subprocess' | 'docker' | 'local'
export type Locale = 'en' | 'zh'

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
  locale: Locale
  dataRetentionDays: number
  autoApprovePlans: boolean
  enableNotifications: boolean
  isSaving: boolean
  saveError: string | null
  isTesting: boolean
  testResult: { ok: boolean; message: string } | null
  updateModel: (config: Partial<ModelConfig>) => void
  updateExecution: (config: Partial<ExecutionConfig>) => void
  updateSearch: (config: Partial<SearchConfig>) => void
  updateBudget: (config: Partial<BudgetConfig>) => void
  setLocale: (locale: Locale) => void
  setDataRetentionDays: (days: number) => void
  setAutoApprovePlans: (value: boolean) => void
  setEnableNotifications: (value: boolean) => void
  loadSettings: () => Promise<void>
  saveSettings: () => Promise<boolean>
  testConnection: () => Promise<void>
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

// The backend normalizes 'local' to 'ollama'; reverse it when hydrating from the server.
const backendToFrontendProvider = (provider: string | null): LlmProvider => {
  if (provider === 'ollama') return 'local'
  const known: LlmProvider[] = ['openai', 'anthropic', 'azure', 'moonshot', 'deepseek', 'qwen', 'local', 'custom']
  return (known.includes(provider as LlmProvider) ? (provider as LlmProvider) : 'custom')
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set, get) => ({
      model: defaultModel,
      execution: defaultExecution,
      search: defaultSearch,
      budget: defaultBudget,
      locale: 'en',
      dataRetentionDays: 0,
      autoApprovePlans: false,
      enableNotifications: true,
      isSaving: false,
      saveError: null,
      isTesting: false,
      testResult: null,

      updateModel: (config) => set((state) => ({ model: { ...state.model, ...config } })),
      updateExecution: (config) => set((state) => ({ execution: { ...state.execution, ...config } })),
      updateSearch: (config) => set((state) => ({ search: { ...state.search, ...config } })),
      updateBudget: (config) => set((state) => ({ budget: { ...state.budget, ...config } })),
      setLocale: (locale) => set({ locale }),
      setDataRetentionDays: (days) => set({ dataRetentionDays: days }),
      setAutoApprovePlans: (value) => set({ autoApprovePlans: value }),
      setEnableNotifications: (value) => set({ enableNotifications: value }),

      loadSettings: async () => {
        try {
          const { data } = await settingsApi.getLlmConfig()
          set((state) => ({
            model: {
              ...state.model,
              provider: backendToFrontendProvider(data.provider),
              model: data.model || state.model.model,
              baseUrl: data.base_url || '',
              temperature: data.temperature,
              maxTokens: data.max_tokens,
              // Never overwrite the in-memory API key from server; server returns masked/null.
            },
            saveError: null,
          }))
        } catch (err: any) {
          set({ saveError: err?.response?.data?.detail || err.message || 'Failed to load settings' })
        }
      },

      saveSettings: async () => {
        set({ isSaving: true, saveError: null })
        try {
          const state = get()
          const { data } = await settingsApi.updateLlmConfig({
            provider: state.model.provider,
            model: state.model.model,
            base_url: state.model.baseUrl || undefined,
            api_key: state.model.apiKey || undefined,
            temperature: state.model.temperature,
            max_tokens: state.model.maxTokens,
          })
          set((state) => ({
            isSaving: false,
            model: {
              ...state.model,
              provider: backendToFrontendProvider(data.provider),
              model: data.model || state.model.model,
              baseUrl: data.base_url || '',
              temperature: data.temperature,
              maxTokens: data.max_tokens,
              // Keep the key in memory so the user can change other fields
              // (model, temperature, etc.) and save again without re-entering it.
              apiKey: state.model.apiKey,
            },
            saveError: null,
          }))
          return true
        } catch (err: any) {
          set({
            isSaving: false,
            saveError: err?.response?.data?.detail || err.message || 'Failed to save settings',
          })
          return false
        }
      },

      testConnection: async () => {
        set({ isTesting: true, testResult: null })
        try {
          const state = get()
          // If the user has not typed an API key into this session, test against
          // the server-side persisted config (which retains the real key) instead
          // of sending an empty key.
          const { data } = state.model.apiKey
            ? await settingsApi.testLlmConnection({
                provider: state.model.provider,
                model: state.model.model,
                base_url: state.model.baseUrl || undefined,
                api_key: state.model.apiKey,
                temperature: state.model.temperature,
                max_tokens: state.model.maxTokens,
              })
            : await settingsApi.testLlmConnection()
          set({
            isTesting: false,
            testResult: {
              ok: data.ok,
              message: data.ok
                ? `Connected to ${data.provider}/${data.model}`
                : data.error || 'Connection test failed',
            },
          })
        } catch (err: any) {
          set({
            isTesting: false,
            testResult: {
              ok: false,
              message: err?.response?.data?.detail || err.message || 'Connection test failed',
            },
          })
        }
      },

      reset: () =>
        set({
          model: defaultModel,
          execution: defaultExecution,
          search: defaultSearch,
          budget: defaultBudget,
          locale: 'en',
          dataRetentionDays: 0,
          autoApprovePlans: false,
          enableNotifications: true,
          isSaving: false,
          saveError: null,
          isTesting: false,
          testResult: null,
        }),
    }),
    {
      name: 'homomics-settings',
      version: 3,
      migrate: (persistedState: any) => {
        // Reset language to English for existing stored settings once.
        if (persistedState && persistedState.locale !== 'en') {
          return { ...persistedState, locale: 'en' }
        }
        return persistedState
      },
      partialize: (state) => ({
        // Only persist UI preferences locally.  LLM credentials live on the server.
        execution: state.execution,
        search: state.search,
        budget: state.budget,
        locale: state.locale,
        dataRetentionDays: state.dataRetentionDays,
        autoApprovePlans: state.autoApprovePlans,
        enableNotifications: state.enableNotifications,
      }),
    }
  )
)

// Hydrate LLM config from the server on store creation.
useSettingsStore.getState().loadSettings()
