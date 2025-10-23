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
  setCurrency: (currency: Currency) => Promise<void>
  clearError: () => void
  updatePortfolioWithNewPrice: (symbol: string, price: number, exchangeRates?: Record<string, number>) => void
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

      setCurrency: async (currency: Currency) => {
        set({ selectedCurrency: currency, loading: true })
        // Refresh data with new currency
        await Promise.all([
          get().fetchPortfolio(),
          get().fetchSummary()
        ])
        // Keep loading state for a bit longer to ensure smooth transition
        setTimeout(() => {
          set({ loading: false })
        }, 200)
      },

      clearError: () => set({ error: null }),

      updatePortfolioWithNewPrice: (symbol: string, usdPrice: number, exchangeRates?: Record<string, number>) => {
        const state = get()
        const { selectedCurrency } = state
        
        // Convert USD price to selected currency if needed
        let convertedPrice = usdPrice
        if (selectedCurrency !== 'USD' && exchangeRates && exchangeRates[selectedCurrency]) {
          convertedPrice = usdPrice * exchangeRates[selectedCurrency]
        }
        
        // Update items with new price for the specific symbol
        const updatedItems = state.items.map(item => {
          if (item.symbol === symbol) {
            // Calculate new values based on the converted price
            const currentValue = item.amount * convertedPrice
            const totalInvestment = (item.amount * item.price_buy) + item.commission
            const pnl = currentValue - totalInvestment
            const pnlPercent = totalInvestment > 0 ? (pnl / totalInvestment) * 100 : 0
            
            return {
              ...item,
              current_price: convertedPrice,
              current_value: currentValue,
              pnl: pnl,
              pnl_percent: pnlPercent,
              updated_at: new Date().toISOString()
            }
          }
          return item
        })
        
        // Update summary with new totals
        const newSummary = updatedItems.reduce((acc, item) => {
          acc.total_invested += (item.amount * item.price_buy) + item.commission
          acc.total_value += item.current_value || 0
          acc.total_pnl += item.pnl || 0
          acc.item_count += 1
          return acc
        }, {
          total_value: 0,
          total_invested: 0,
          total_pnl: 0,
          total_pnl_percent: 0,
          currency: selectedCurrency,
          item_count: 0
        })
        
        newSummary.total_pnl_percent = newSummary.total_invested > 0 
          ? (newSummary.total_pnl / newSummary.total_invested) * 100 
          : 0
        
        set({ 
          items: updatedItems,
          summary: newSummary
        })
      }
    }),
    {
      name: 'portfolio-store'
    }
  )
)
