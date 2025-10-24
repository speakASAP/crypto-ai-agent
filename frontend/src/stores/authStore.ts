import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import {
  User,
  UserLogin,
  UserRegister,
  TokenResponse,
  PasswordResetRequest,
  PasswordResetConfirm,
  UserProfileUpdate,
  PasswordChange
} from '@/types/auth'
import { apiClient } from '@/lib/api'

// Cookie storage for server-side access
const cookieStorage = {
  getItem: (name: string): string | null => {
    if (typeof document === 'undefined') return null
    const value = `; ${document.cookie}`
    const parts = value.split(`; ${name}=`)
    if (parts.length === 2) return parts.pop()?.split(';').shift() || null
    return null
  },
  setItem: (name: string, value: string): void => {
    if (typeof document === 'undefined') return
    document.cookie = `${name}=${value}; path=/; max-age=${7 * 24 * 60 * 60}; samesite=lax`
  },
  removeItem: (name: string): void => {
    if (typeof document === 'undefined') return
    document.cookie = `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT`
  }
}

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: User | null
  isAuthenticated: boolean
  isHydrated: boolean
  loading: boolean
  error: string | null
  
  // Actions
  login: (credentials: UserLogin) => Promise<void>
  logout: () => void
  refreshAccessToken: () => Promise<void>
  register: (userData: UserRegister) => Promise<void>
  requestPasswordReset: (email: string) => Promise<void>
  confirmPasswordReset: (token: string, newPassword: string) => Promise<void>
  updateProfile: (updateData: UserProfileUpdate) => Promise<User>
  changePassword: (passwordChange: PasswordChange) => Promise<void>
  setUser: (user: User) => void
  clearError: () => void
  setHydrated: (hydrated: boolean) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
      isHydrated: false,
      loading: false,
      error: null,

      login: async (credentials: UserLogin) => {
        set({ loading: true, error: null })
        try {
          const response = await apiClient.login(credentials)
          set({
            accessToken: response.access_token,
            refreshToken: response.refresh_token,
            user: response.user,
            isAuthenticated: true,
            loading: false,
          })
        } catch (error: any) {
          set({ 
            error: error.message || 'Login failed', 
            loading: false 
          })
          throw error
        }
      },

      logout: () => {
        set({ 
          accessToken: null, 
          refreshToken: null, 
          user: null, 
          isAuthenticated: false,
          error: null
        })
      },

      refreshAccessToken: async () => {
        const currentRefreshToken = get().refreshToken
        if (!currentRefreshToken) {
          get().logout()
          throw new Error("No refresh token available")
        }
        try {
          const response = await apiClient.refreshToken(currentRefreshToken)
          set({
            accessToken: response.access_token,
            refreshToken: response.refresh_token,
            user: response.user,
            isAuthenticated: true,
          })
        } catch (error) {
          get().logout()
          throw error
        }
      },

      register: async (userData: UserRegister) => {
        set({ loading: true, error: null })
        try {
          const response = await apiClient.register(userData)
          set({
            accessToken: response.access_token,
            refreshToken: response.refresh_token,
            user: response.user,
            isAuthenticated: true,
            loading: false,
          })
        } catch (error: any) {
          set({ 
            error: error.message || 'Registration failed', 
            loading: false 
          })
          throw error
        }
      },

      requestPasswordReset: async (email: string) => {
        set({ loading: true, error: null })
        try {
          await apiClient.requestPasswordReset(email)
          set({ loading: false })
        } catch (error: any) {
          set({ 
            error: error.message || 'Password reset request failed', 
            loading: false 
          })
          throw error
        }
      },

      confirmPasswordReset: async (token: string, newPassword: string) => {
        set({ loading: true, error: null })
        try {
          await apiClient.confirmPasswordReset(token, newPassword)
          set({ loading: false })
        } catch (error: any) {
          set({ 
            error: error.message || 'Password reset failed', 
            loading: false 
          })
          throw error
        }
      },

      updateProfile: async (updateData: UserProfileUpdate) => {
        set({ loading: true, error: null })
        try {
          const updatedUser = await apiClient.updateProfile(updateData)
          set({ user: updatedUser, loading: false })
          return updatedUser
        } catch (error: any) {
          set({ 
            error: error.message || 'Profile update failed', 
            loading: false 
          })
          throw error
        }
      },

      changePassword: async (passwordChange: PasswordChange) => {
        set({ loading: true, error: null })
        try {
          await apiClient.changePassword(passwordChange)
          set({ loading: false })
        } catch (error: any) {
          set({ 
            error: error.message || 'Password change failed', 
            loading: false 
          })
          throw error
        }
      },

      setUser: (user: User) => {
        set({ user })
      },

      clearError: () => {
        set({ error: null })
      },

      setHydrated: (hydrated: boolean) => {
        set({ isHydrated: hydrated })
      },
    }),
        {
          name: 'auth-storage',
          storage: createJSONStorage(() => ({
            getItem: (name: string) => {
              // Try localStorage first, then cookies
              if (typeof window !== 'undefined') {
                return localStorage.getItem(name) || cookieStorage.getItem(name)
              }
              return cookieStorage.getItem(name)
            },
            setItem: (name: string, value: string) => {
              if (typeof window !== 'undefined') {
                localStorage.setItem(name, value)
              }
              cookieStorage.setItem(name, value)
            },
            removeItem: (name: string) => {
              if (typeof window !== 'undefined') {
                localStorage.removeItem(name)
              }
              cookieStorage.removeItem(name)
            }
          })),
          onRehydrateStorage: () => (state) => {
            state?.setHydrated(true)
          },
        }
  )
)
