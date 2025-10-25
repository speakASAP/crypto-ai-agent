import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import { PortfolioItem, PortfolioCreate, PortfolioUpdate, PortfolioSummary, Currency } from '@/types'
import { apiClient } from '@/lib/api'
import { refreshCryptoPrices } from '@/lib/refreshUtils'

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
  setCurrencyFromUserPreference: (currency: Currency) => void
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
          
          // Trigger the same refresh action as the refresh button
          try {
            await refreshCryptoPrices()
            // Reload portfolio data with new prices (same as refresh button)
            get().fetchPortfolio()
            get().fetchSummary()
          } catch (refreshError) {
            console.warn('Price refresh failed, but portfolio item was created:', refreshError)
            // Still refresh summary even if price refresh fails
            get().fetchSummary()
          }
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
        
        // Save currency preference to user profile
        try {
          await apiClient.updateProfile({ preferred_currency: currency })
        } catch (error) {
          console.error('Failed to save currency preference:', error)
        }
        
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

      setCurrencyFromUserPreference: (currency: Currency) => {
        set({ selectedCurrency: currency })
      },

      clearError: () => set({ error: null }),

      updatePortfolioWithNewPrice: (symbol: string, usdPrice: number, exchangeRates?: Record<string, number>) => {
        const state = get()
        const { selectedCurrency } = state
        
        // Update items with new price for the specific symbol
        const updatedItems = state.items.map(item => {
          if (item.symbol === symbol) {
            // Use USD values for calculations if available
            const priceBuyUsd = item.price_buy_usd || item.price_buy
            const commissionUsd = item.commission_usd || item.commission
            
            // Calculate USD values
            const currentValueUsd = item.amount * usdPrice
            const totalInvestmentUsd = (item.amount * priceBuyUsd) + commissionUsd
            const pnlUsd = currentValueUsd - totalInvestmentUsd
            const pnlPercentUsd = totalInvestmentUsd > 0 ? (pnlUsd / totalInvestmentUsd) * 100 : 0
            
            // Convert to display currency for display
            let currentPriceDisplay = usdPrice
            let currentValueDisplay = currentValueUsd
            let pnlDisplay = pnlUsd
            
            if (selectedCurrency !== 'USD' && exchangeRates && exchangeRates[selectedCurrency]) {
              currentPriceDisplay = usdPrice * exchangeRates[selectedCurrency]
              currentValueDisplay = currentValueUsd * exchangeRates[selectedCurrency]
              pnlDisplay = pnlUsd * exchangeRates[selectedCurrency]
            }
            
            return {
              ...item,
              current_price: currentPriceDisplay,
              current_value: currentValueDisplay,
              pnl: pnlDisplay,
              pnl_percent: pnlPercentUsd, // Use USD percentage for accuracy
              current_price_usd: usdPrice,
              current_value_usd: currentValueUsd,
              pnl_usd: pnlUsd,
              pnl_percent_usd: pnlPercentUsd,
              updated_at: new Date().toISOString()
            }
          }
          return item
        })
        
        // Update summary with new totals using USD values for accuracy
        const newSummary = updatedItems.reduce((acc, item) => {
          const priceBuyUsd = item.price_buy_usd || item.price_buy
          const commissionUsd = item.commission_usd || item.commission
          const totalInvestmentUsd = (item.amount * priceBuyUsd) + commissionUsd
          const currentValueUsd = item.current_value_usd || item.current_value || 0
          const pnlUsd = item.pnl_usd || item.pnl || 0
          
          acc.total_invested += totalInvestmentUsd
          acc.total_value += currentValueUsd
          acc.total_pnl += pnlUsd
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
        
        // Convert summary values to display currency
        if (selectedCurrency !== 'USD' && exchangeRates && exchangeRates[selectedCurrency]) {
          const rate = exchangeRates[selectedCurrency]
          newSummary.total_value = newSummary.total_value * rate
          newSummary.total_invested = newSummary.total_invested * rate
          newSummary.total_pnl = newSummary.total_pnl * rate
        }
        
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
