import { create } from 'zustand'
import type { AnalysisTemplate } from '@/types/api'
import { analysisTemplateApi } from '@/services/api'

interface AnalysisTemplateState {
  templates: AnalysisTemplate[]
  loading: boolean
  error: string | null

  fetchTemplates: () => Promise<void>
  clearError: () => void
}

export const useAnalysisTemplateStore = create<AnalysisTemplateState>((set) => ({
  templates: [],
  loading: false,
  error: null,

  fetchTemplates: async () => {
    set({ loading: true, error: null })
    try {
      const response = await analysisTemplateApi.listTemplates()
      const templates = Array.isArray(response.data)
        ? response.data
        : response.data?.templates ?? []
      set({ templates, loading: false })
    } catch (err) {
      set({
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to load analysis templates',
      })
    }
  },

  clearError: () => set({ error: null }),
}))
