import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import { PriceAlert, PriceAlertCreate, PriceAlertUpdate, AlertHistory } from '../types'
import { apiClient } from '../lib/api'
import { logger } from '../lib/logger'

interface AlertsState {
  alerts: PriceAlert[]
  history: AlertHistory[]
  loading: boolean
  error: string | null
  
  // Actions
  fetchAlerts: (activeOnly?: boolean) => Promise<void>
  createAlert: (alert: PriceAlertCreate) => Promise<void>
  updateAlert: (id: number, alert: PriceAlertUpdate) => Promise<void>
  deleteAlert: (id: number) => Promise<void>
  fetchHistory: (limit?: number) => Promise<void>
  triggerAlert: (id: number, currentPrice: number) => Promise<void>
  clearError: () => void
}

export const useAlertsStore = create<AlertsState>()(
  devtools(
    (set, get) => ({
      alerts: [],
      history: [],
      loading: false,
      error: null,

      fetchAlerts: async (activeOnly = true) => {
        set({ loading: true, error: null })
        
        const maxRetries = 3
        const initialDelay = 2000 // 2 seconds
        
        for (let attempt = 0; attempt <= maxRetries; attempt++) {
          try {
            const alerts = await apiClient.getAlerts(activeOnly)
            set({ alerts, loading: false })
            return // Success - exit retry loop
          } catch (error: any) {
            const status = error?.response?.status || error?.status
            
            // Handle 503 Service Unavailable with retry
            if (status === 503 && attempt < maxRetries) {
              const delay = initialDelay * Math.pow(2, attempt) // 2s, 4s, 8s
              logger.debug(`Service Unavailable (503) for alerts, retrying in ${delay}ms (attempt ${attempt + 1}/${maxRetries + 1})`)
              
              // Wait before retrying
              await new Promise(resolve => setTimeout(resolve, delay))
              continue // Retry
            } else {
              // Non-503 error or max retries exceeded
              // Don't set error state for 503 errors (service unavailable is temporary)
              if (status !== 503) {
                set({ 
                  error: error.message || 'Failed to fetch alerts', 
                  loading: false 
                })
              } else {
                // Max retries exceeded for 503, but don't show error to user
                set({ loading: false })
              }
              return // Exit retry loop
            }
          }
        }
      },

      createAlert: async (alert: PriceAlertCreate) => {
        set({ loading: true, error: null })
        try {
          const newAlert = await apiClient.createAlert(alert)
          set(state => ({ 
            alerts: [...state.alerts, newAlert], 
            loading: false 
          }))
        } catch (error: any) {
          set({ 
            error: error.message || 'Failed to create alert', 
            loading: false 
          })
        }
      },

      updateAlert: async (id: number, alert: PriceAlertUpdate) => {
        set({ loading: true, error: null })
        try {
          const updatedAlert = await apiClient.updateAlert(id, alert)
          set(state => ({
            alerts: state.alerts.map(a => a.id === id ? updatedAlert : a),
            loading: false
          }))
        } catch (error: any) {
          set({ 
            error: error.message || 'Failed to update alert', 
            loading: false 
          })
        }
      },

      deleteAlert: async (id: number) => {
        set({ loading: true, error: null })
        try {
          await apiClient.deleteAlert(id)
          set(state => ({
            alerts: state.alerts.filter(a => a.id !== id),
            loading: false
          }))
        } catch (error: any) {
          set({ 
            error: error.message || 'Failed to delete alert', 
            loading: false 
          })
        }
      },

      fetchHistory: async (limit = 100) => {
        try {
          const history = await apiClient.getAlertHistory(limit)
          set({ history })
        } catch (error: any) {
          logger.error('Failed to fetch alert history:', error)
        }
      },

      triggerAlert: async (id: number, currentPrice: number) => {
        try {
          await apiClient.triggerAlert(id, currentPrice)
          // Refresh history to show the triggered alert
          get().fetchHistory()
        } catch (error: any) {
          set({ 
            error: error.message || 'Failed to trigger alert'
          })
        }
      },

      clearError: () => set({ error: null })
    }),
    {
      name: 'alerts-store'
    }
  )
)
