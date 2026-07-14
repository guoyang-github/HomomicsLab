import { create } from 'zustand'

export type OverlayType = 'report' | 'workflow' | 'figure' | null

interface OverlayState {
  open: OverlayType
  params: Record<string, unknown>
  openReport: (params?: Record<string, unknown>) => void
  openWorkflow: (params?: Record<string, unknown>) => void
  openFigure: (params?: Record<string, unknown>) => void
  closeOverlay: () => void
}

export const useOverlayStore = create<OverlayState>((set) => ({
  open: null,
  params: {},
  openReport: (params = {}) => set({ open: 'report', params }),
  openWorkflow: (params = {}) => set({ open: 'workflow', params }),
  openFigure: (params = {}) => set({ open: 'figure', params }),
  closeOverlay: () => set({ open: null, params: {} }),
}))
