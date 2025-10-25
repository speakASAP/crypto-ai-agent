import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import { TrackedSymbol, TrackedSymbolCreate, TrackedSymbolUpdate, CryptoSymbol, SymbolPrice } from '@/types'
import { apiClient } from '@/lib/api'

interface SymbolsState {
  trackedSymbols: TrackedSymbol[]
  cryptoSymbols: CryptoSymbol[]
  symbolPrices: Record<string, SymbolPrice>
  loading: boolean
  error: string | null
  
  // Actions
  fetchTrackedSymbols: (activeOnly?: boolean) => Promise<void>
  addTrackedSymbol: (symbol: TrackedSymbolCreate) => Promise<void>
  updateTrackedSymbol: (symbol: string, update: TrackedSymbolUpdate) => Promise<void>
  removeTrackedSymbol: (symbol: string) => Promise<void>
  fetchCryptoSymbols: (limit?: number) => Promise<void>
  fetchSymbolPrices: (symbols: string[]) => Promise<void>
  clearError: () => void
}

export const useSymbolsStore = create<SymbolsState>()(
  devtools(
    (set, get) => ({
      trackedSymbols: [],
      cryptoSymbols: [],
      symbolPrices: {},
      loading: false,
      error: null,

      fetchTrackedSymbols: async (activeOnly = true) => {
        set({ loading: true, error: null })
        try {
          const trackedSymbols = await apiClient.getTrackedSymbols(activeOnly)
          set({ trackedSymbols, loading: false })
        } catch (error: any) {
          set({ 
            error: error.message || 'Failed to fetch tracked symbols', 
            loading: false 
          })
        }
      },

      addTrackedSymbol: async (symbol: TrackedSymbolCreate) => {
        set({ loading: true, error: null })
        try {
          const newSymbol = await apiClient.addTrackedSymbol(symbol)
          set(state => ({ 
            trackedSymbols: [...state.trackedSymbols, newSymbol], 
            loading: false 
          }))
        } catch (error: any) {
          set({ 
            error: error.message || 'Failed to add tracked symbol', 
            loading: false 
          })
        }
      },

      updateTrackedSymbol: async (symbol: string, update: TrackedSymbolUpdate) => {
        set({ loading: true, error: null })
        try {
          const updatedSymbol = await apiClient.updateTrackedSymbol(symbol, update)
          set(state => ({
            trackedSymbols: state.trackedSymbols.map(s => 
              s.symbol === symbol ? updatedSymbol : s
            ),
            loading: false
          }))
        } catch (error: any) {
          set({ 
            error: error.message || 'Failed to update tracked symbol', 
            loading: false 
          })
        }
      },

      removeTrackedSymbol: async (symbol: string) => {
        set({ loading: true, error: null })
        try {
          await apiClient.removeTrackedSymbol(symbol)
          set(state => ({
            trackedSymbols: state.trackedSymbols.filter(s => s.symbol !== symbol),
            loading: false
          }))
        } catch (error: any) {
          set({ 
            error: error.message || 'Failed to remove tracked symbol', 
            loading: false 
          })
        }
      },

      fetchCryptoSymbols: async (limit = 500) => {
        try {
          const cryptoSymbols = await apiClient.getCryptoSymbols(limit)
          set({ cryptoSymbols })
        } catch (error: any) {
          console.error('Failed to fetch crypto symbols:', error)
        }
      },

      fetchSymbolPrices: async (symbols: string[]) => {
        try {
          const prices = await apiClient.getSymbolPrices(symbols)
          const priceMap = prices.reduce((acc, price) => {
            acc[price.symbol] = price
            return acc
          }, {} as Record<string, SymbolPrice>)
          
          set(state => ({
            symbolPrices: { ...state.symbolPrices, ...priceMap }
          }))
        } catch (error: any) {
          console.error('Failed to fetch symbol prices:', error)
        }
      },

      clearError: () => set({ error: null })
    }),
    {
      name: 'symbols-store'
    }
  )
)
