import { create } from 'zustand'
import type { TaskNode, TaskProgress, TaskStatus } from '@/types/tasks'

interface TaskState {
  tasks: TaskNode[]
  progress: TaskProgress
  selectedTaskId: string | null

  setTaskTree: (tasks: TaskNode[]) => void
  updateTaskStatus: (taskId: string, status: TaskStatus) => void
  updateTaskResult: (taskId: string, result: Record<string, unknown>) => void
  setProgress: (progress: TaskProgress) => void
  selectTask: (taskId: string | null) => void
}

const emptyProgress: TaskProgress = {
  total: 0,
  pending: 0,
  running: 0,
  completed: 0,
  failed: 0,
  awaiting_human: 0,
  percent: 0,
}

export const useTaskStore = create<TaskState>((set) => ({
  tasks: [],
  progress: emptyProgress,
  selectedTaskId: null,

  setTaskTree: (tasks) => set({ tasks }),

  updateTaskStatus: (taskId, status) =>
    set((state) => ({
      tasks: state.tasks.map((t) =>
        t.id === taskId ? { ...t, status } : t
      ),
    })),

  updateTaskResult: (taskId, result) =>
    set((state) => ({
      tasks: state.tasks.map((t) =>
        t.id === taskId ? { ...t, result } : t
      ),
    })),

  setProgress: (progress) => set({ progress }),
  selectTask: (selectedTaskId) => set({ selectedTaskId }),
}))
