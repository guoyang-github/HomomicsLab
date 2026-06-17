import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useProjectStore } from './projectStore'
import { projectApi } from '@/services/api'

describe('projectStore', () => {
  beforeEach(() => {
    useProjectStore.setState({
      projects: [],
      currentProjectId: 'default',
      loading: false,
      error: null,
    })
    vi.restoreAllMocks()
  })

  it('should default to the local default project', () => {
    const state = useProjectStore.getState()
    expect(state.currentProjectId).toBe('default')
    expect(state.projects).toEqual([])
  })

  it('should fetch and store projects', async () => {
    const projects = [
      { id: 'proj_1', name: 'Project One', description: '', created_at: '', updated_at: '' },
    ]
    vi.spyOn(projectApi, 'listProjects').mockResolvedValue({ data: projects } as any)

    await useProjectStore.getState().fetchProjects()

    const state = useProjectStore.getState()
    expect(state.projects).toEqual(projects)
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('should handle fetch errors', async () => {
    vi.spyOn(projectApi, 'listProjects').mockRejectedValue(new Error('network error'))

    await useProjectStore.getState().fetchProjects()

    const state = useProjectStore.getState()
    expect(state.projects).toEqual([])
    expect(state.error).toBe('network error')
  })

  it('should create a project and select it', async () => {
    const newProject = { id: 'proj_new', name: 'New', description: '', created_at: '', updated_at: '' }
    vi.spyOn(projectApi, 'createProject').mockResolvedValue({ data: newProject } as any)

    const result = await useProjectStore.getState().createProject('New', '')

    expect(result).toEqual(newProject)
    const state = useProjectStore.getState()
    expect(state.projects).toContainEqual(newProject)
    expect(state.currentProjectId).toBe('proj_new')
  })

  it('should allow setting the current project', () => {
    useProjectStore.getState().setCurrentProject('proj_2')
    expect(useProjectStore.getState().currentProjectId).toBe('proj_2')
  })
})
