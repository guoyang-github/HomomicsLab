import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Project } from '@/types/api'
import { projectApi } from '@/services/api'

interface ProjectState {
  projects: Project[]
  currentProjectId: string
  loading: boolean
  error: string | null

  fetchProjects: () => Promise<void>
  createProject: (name: string, description?: string) => Promise<Project | null>
  setCurrentProject: (id: string) => void
  clearError: () => void
}

export const useProjectStore = create<ProjectState>()(
  persist(
    (set, get) => ({
      projects: [],
      currentProjectId: 'default',
      loading: false,
      error: null,

      fetchProjects: async () => {
        set({ loading: true, error: null })
        try {
          const response = await projectApi.listProjects()
          const projects = response.data
          set({ projects, loading: false })
          // If current project is not in the list and not the local default,
          // fall back to the first available project.
          const { currentProjectId } = get()
          if (
            currentProjectId !== 'default' &&
            projects.length > 0 &&
            !projects.some((p) => p.id === currentProjectId)
          ) {
            set({ currentProjectId: projects[0].id })
          }
        } catch (err) {
          set({
            loading: false,
            error: err instanceof Error ? err.message : 'Failed to load projects',
          })
        }
      },

      createProject: async (name, description = '') => {
        set({ loading: true, error: null })
        try {
          const response = await projectApi.createProject({ name, description })
          const project = response.data
          set((state) => ({
            projects: [project, ...state.projects],
            currentProjectId: project.id,
            loading: false,
          }))
          return project
        } catch (err) {
          set({
            loading: false,
            error: err instanceof Error ? err.message : 'Failed to create project',
          })
          return null
        }
      },

      setCurrentProject: (id) => set({ currentProjectId: id }),
      clearError: () => set({ error: null }),
    }),
    {
      name: 'homomics-projects',
      partialize: (state) => ({
        currentProjectId: state.currentProjectId,
      }),
    }
  )
)
