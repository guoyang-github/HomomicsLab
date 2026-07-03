import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface AuthState {
  token: string
  setToken: (token: string) => void
  clearToken: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: '',
      setToken: (token) => set({ token }),
      clearToken: () => set({ token: '' }),
    }),
    { name: 'homomics-auth' },
  ),
)
