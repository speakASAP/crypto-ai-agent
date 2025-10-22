import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import { PriceAlert, PriceAlertCreate, PriceAlertUpdate, AlertHistory } from '@/types'
import { apiClient } from '@/lib/api'

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
        try {
          const alerts = await apiClient.getAlerts(activeOnly)
          set({ alerts, loading: false })
        } catch (error: any) {
          set({ 
            error: error.message || 'Failed to fetch alerts', 
            loading: false 
          })
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
          console.error('Failed to fetch alert history:', error)
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
