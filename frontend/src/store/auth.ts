import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User {
  id: number
  username: string
  email: string
  nickname: string | null
  avatar: string | null
}

interface AuthStore {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  register: (data: RegisterData) => Promise<void>
  logout: () => void
  updateUser: (data: Partial<User>) => void
  setToken: (token: string) => void
  checkAuth: () => void
}

interface RegisterData {
  username: string
  email: string
  password: string
  nickname?: string
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,

      login: async (username: string, password: string) => {
        const response = await fetch('/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password }),
        })
        const result = await response.json()
        if (result.code === 0) {
          set({
            user: result.data.user,
            token: result.data.access_token,
            isAuthenticated: true,
          })
        } else {
          throw new Error(result.message || '登录失败')
        }
      },

      register: async (data: RegisterData) => {
        const response = await fetch('/api/v1/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
        })
        const result = await response.json()
        if (result.code !== 0) {
          throw new Error(result.message || '注册失败')
        }
      },

      logout: () => {
        set({
          user: null,
          token: null,
          isAuthenticated: false,
        })
        // 清除 localStorage 中的 token
        localStorage.removeItem('token')
      },

      updateUser: (data: Partial<User>) => {
        set((state) => ({
          user: state.user ? { ...state.user, ...data } : null,
        }))
      },

      setToken: (token: string) => {
        set({ token, isAuthenticated: true })
        // 同时保存到 localStorage
        localStorage.setItem('token', token)
      },

      checkAuth: () => {
        const { token } = get()
        const isAuthenticated = !!token
        if (get().isAuthenticated !== isAuthenticated) {
          set({ isAuthenticated })
        }
      },
    }),
    {
      name: 'auth-storage',
      onRehydrateStorage: () => (state) => {
        // 恢复时检查认证状态
        if (state) {
          state.isAuthenticated = !!state.token
          // 同时恢复 localStorage 中的 token
          if (state.token) {
            localStorage.setItem('token', state.token)
          }
        }
      },
    }
  )
)