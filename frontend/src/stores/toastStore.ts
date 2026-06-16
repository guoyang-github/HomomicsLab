import { create } from 'zustand'
import type { Toast, ToastType } from '@/components/ui/Toast'

interface ToastState {
  toasts: Toast[]
  addToast: (toast: Omit<Toast, 'id'>) => string
  removeToast: (id: string) => void
  clearToasts: () => void
}

let toastIdCounter = 0

function generateId() {
  return `toast_${Date.now()}_${++toastIdCounter}`
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  addToast: (toast) => {
    const id = generateId()
    set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }))
    return id
  },
  removeToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
  clearToasts: () => set({ toasts: [] }),
}))

export function toast(message: string, type: ToastType = 'info', title?: string, duration?: number) {
  return useToastStore.getState().addToast({ message, type, title, duration })
}

export function toastSuccess(message: string, title?: string) {
  return toast(message, 'success', title)
}

export function toastError(message: string, title?: string) {
  return toast(message, 'error', title)
}

export function toastWarning(message: string, title?: string) {
  return toast(message, 'warning', title)
}

export function toastInfo(message: string, title?: string) {
  return toast(message, 'info', title)
}
