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
import { usePortfolioStore } from './portfolioStore'

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
  deleteAccount: (confirmationText: string) => Promise<void>
  testTelegramConnection: () => Promise<{ message: string; success: boolean }>
  setUser: (user: User) => void
  clearError: () => void
  setHydrated: (hydrated: boolean) => void
}

// Helper function to calculate authentication state
const calculateIsAuthenticated = (accessToken: string | null, user: User | null): boolean => {
  return !!(accessToken && user)
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
            isAuthenticated: calculateIsAuthenticated(response.access_token, response.user),
            loading: false,
          })
          
          // Set user's preferred currency in portfolio store
          const portfolioStore = usePortfolioStore.getState()
          portfolioStore.setCurrencyFromUserPreference(response.user.preferred_currency as any)
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
            isAuthenticated: calculateIsAuthenticated(response.access_token, response.user),
          })
          
          // Set user's preferred currency in portfolio store
          const portfolioStore = usePortfolioStore.getState()
          portfolioStore.setCurrencyFromUserPreference(response.user.preferred_currency as any)
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
            isAuthenticated: calculateIsAuthenticated(response.access_token, response.user),
            loading: false,
          })
          
          // Set user's preferred currency in portfolio store
          const portfolioStore = usePortfolioStore.getState()
          portfolioStore.setCurrencyFromUserPreference(response.user.preferred_currency as any)
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

      deleteAccount: async (confirmationText: string) => {
        set({ loading: true, error: null })
        try {
          await apiClient.deleteAccount(confirmationText)
          // Clear all auth state after successful deletion
          set({ 
            accessToken: null, 
            refreshToken: null, 
            user: null, 
            loading: false,
            error: null
          })
        } catch (error: any) {
          set({ 
            error: error.message || 'Account deletion failed', 
            loading: false 
          })
          throw error
        }
      },

      testTelegramConnection: async () => {
        set({ loading: true, error: null })
        try {
          const result = await apiClient.testTelegramConnection()
          set({ loading: false })
          return result
        } catch (error: any) {
          set({ 
            error: error.message || 'Telegram test failed', 
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
            // Set hydrated to true after store rehydration completes
            if (state) {
              // Calculate authentication state based on rehydrated data
              state.isAuthenticated = calculateIsAuthenticated(state.accessToken, state.user)
              // Ensure we have a valid state before setting hydrated
              state.setHydrated(true)
            }
          },
          partialize: (state) => ({
            accessToken: state.accessToken,
            refreshToken: state.refreshToken,
            user: state.user,
            // Don't persist isAuthenticated as it's computed
            // Don't persist isHydrated as it should be false on initial load
          }),
        }
  )
)
