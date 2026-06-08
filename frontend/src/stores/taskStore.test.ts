import { describe, it, expect } from 'vitest'
import { useTaskStore } from './taskStore'
import type { TaskNode } from '@/types/tasks'

describe('taskStore', () => {
  it('should update task tree', () => {
    const tree: TaskNode[] = [
      { id: '1', name: 'qc', description: 'QC', phase: 'pre', status: 'pending', dependencies: [], skills_required: [], estimated_duration_minutes: 10, parameters: {} },
    ]

    useTaskStore.getState().setTaskTree(tree)
    expect(useTaskStore.getState().tasks).toHaveLength(1)
    expect(useTaskStore.getState().tasks[0].name).toBe('qc')
  })

  it('should update task status', () => {
    const tree: TaskNode[] = [
      { id: '1', name: 'qc', description: 'QC', phase: 'pre', status: 'pending', dependencies: [], skills_required: [], estimated_duration_minutes: 10, parameters: {} },
    ]

    useTaskStore.getState().setTaskTree(tree)
    useTaskStore.getState().updateTaskStatus('1', 'running')

    expect(useTaskStore.getState().tasks[0].status).toBe('running')
  })
})
