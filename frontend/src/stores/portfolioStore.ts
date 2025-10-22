import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import { PortfolioItem, PortfolioCreate, PortfolioUpdate, PortfolioSummary, Currency } from '@/types'
import { apiClient } from '@/lib/api'

interface PortfolioState {
  items: PortfolioItem[]
  summary: PortfolioSummary | null
  selectedCurrency: Currency
  loading: boolean
  error: string | null
  
  // Actions
  fetchPortfolio: () => Promise<void>
  createItem: (item: PortfolioCreate) => Promise<void>
  updateItem: (id: number, item: PortfolioUpdate) => Promise<void>
  deleteItem: (id: number) => Promise<void>
  fetchSummary: () => Promise<void>
  setCurrency: (currency: Currency) => void
  clearError: () => void
}

export const usePortfolioStore = create<PortfolioState>()(
  devtools(
    (set, get) => ({
      items: [],
      summary: null,
      selectedCurrency: 'USD',
      loading: false,
      error: null,

      fetchPortfolio: async () => {
        set({ loading: true, error: null })
        try {
          const { selectedCurrency } = get()
          const items = await apiClient.getPortfolio(selectedCurrency)
          set({ items, loading: false })
        } catch (error: any) {
          set({ 
            error: error.message || 'Failed to fetch portfolio', 
            loading: false 
          })
        }
      },

      createItem: async (item: PortfolioCreate) => {
        set({ loading: true, error: null })
        try {
          const newItem = await apiClient.createPortfolioItem(item)
          set(state => ({ 
            items: [...state.items, newItem], 
            loading: false 
          }))
          // Refresh summary
          get().fetchSummary()
        } catch (error: any) {
          set({ 
            error: error.message || 'Failed to create portfolio item', 
            loading: false 
          })
        }
      },

      updateItem: async (id: number, item: PortfolioUpdate) => {
        set({ loading: true, error: null })
        try {
          const updatedItem = await apiClient.updatePortfolioItem(id, item)
          set(state => ({
            items: state.items.map(i => i.id === id ? updatedItem : i),
            loading: false
          }))
          // Refresh summary
          get().fetchSummary()
        } catch (error: any) {
          set({ 
            error: error.message || 'Failed to update portfolio item', 
            loading: false 
          })
        }
      },

      deleteItem: async (id: number) => {
        set({ loading: true, error: null })
        try {
          await apiClient.deletePortfolioItem(id)
          set(state => ({
            items: state.items.filter(i => i.id !== id),
            loading: false
          }))
          // Refresh summary
          get().fetchSummary()
        } catch (error: any) {
          set({ 
            error: error.message || 'Failed to delete portfolio item', 
            loading: false 
          })
        }
      },

      fetchSummary: async () => {
        try {
          const { selectedCurrency } = get()
          const summary = await apiClient.getPortfolioSummary(selectedCurrency)
          set({ summary })
        } catch (error: any) {
          console.error('Failed to fetch portfolio summary:', error)
        }
      },

      setCurrency: (currency: Currency) => {
        set({ selectedCurrency: currency })
        // Refresh data with new currency
        get().fetchPortfolio()
        get().fetchSummary()
      },

      clearError: () => set({ error: null })
    }),
    {
      name: 'portfolio-store'
    }
  )
)
