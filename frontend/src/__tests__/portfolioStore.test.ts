/**
 * Unit tests for Portfolio Store
 */
import { renderHook, act } from '@testing-library/react'
import { usePortfolioStore } from '../stores/portfolioStore'
import { apiClient } from '../lib/api'

// Mock the API client
jest.mock('../lib/api', () => ({
  apiClient: {
    getPortfolio: jest.fn(),
    createPortfolioItem: jest.fn(),
    updatePortfolioItem: jest.fn(),
    deletePortfolioItem: jest.fn(),
    getPortfolioSummary: jest.fn()
  }
}))

const mockApiClient = apiClient as jest.Mocked<typeof apiClient>

describe('Portfolio Store', () => {
  beforeEach(() => {
    // Reset store state before each test
    usePortfolioStore.getState().items = []
    usePortfolioStore.getState().summary = null
    usePortfolioStore.getState().error = null
    usePortfolioStore.getState().loading = false
  })

  describe('Initial State', () => {
    it('should have correct initial state', () => {
      const { result } = renderHook(() => usePortfolioStore())
      
      expect(result.current.items).toEqual([])
      expect(result.current.summary).toBeNull()
      expect(result.current.selectedCurrency).toBe('USD')
      expect(result.current.loading).toBe(false)
      expect(result.current.error).toBeNull()
    })
  })

  describe('fetchPortfolio', () => {
    it('should fetch portfolio successfully', async () => {
      const mockPortfolio = [
        {
          id: 1,
          symbol: 'BTC',
          amount: 1.5,
          price_buy: 50000,
          base_currency: 'USD',
          commission: 0,
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z'
        }
      ]

      mockApiClient.getPortfolio.mockResolvedValue(mockPortfolio)

      const { result } = renderHook(() => usePortfolioStore())

      await act(async () => {
        await result.current.fetchPortfolio()
      })

      expect(result.current.items).toEqual(mockPortfolio)
      expect(result.current.loading).toBe(false)
      expect(result.current.error).toBeNull()
    })

    it('should handle fetch portfolio error', async () => {
      const errorMessage = 'Failed to fetch portfolio'
      mockApiClient.getPortfolio.mockRejectedValue(new Error(errorMessage))

      const { result } = renderHook(() => usePortfolioStore())

      await act(async () => {
        await result.current.fetchPortfolio()
      })

      expect(result.current.items).toEqual([])
      expect(result.current.loading).toBe(false)
      expect(result.current.error).toBe(errorMessage)
    })
  })

  describe('createItem', () => {
    it('should create portfolio item successfully', async () => {
      const newItem = {
        symbol: 'BTC',
        amount: 1.0,
        price_buy: 50000,
        base_currency: 'USD',
        commission: 0
      }

      const createdItem = {
        id: 1,
        ...newItem,
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-01T00:00:00Z'
      }

      mockApiClient.createPortfolioItem.mockResolvedValue(createdItem)
      mockApiClient.getPortfolioSummary.mockResolvedValue({
        total_value: 50000,
        total_pnl: 0,
        total_pnl_percent: 0,
        currency: 'USD',
        item_count: 1
      })

      const { result } = renderHook(() => usePortfolioStore())

      await act(async () => {
        await result.current.createItem(newItem)
      })

      expect(result.current.items).toContain(createdItem)
      expect(result.current.loading).toBe(false)
      expect(result.current.error).toBeNull()
    })

    it('should handle create item error', async () => {
      const newItem = {
        symbol: 'BTC',
        amount: 1.0,
        price_buy: 50000,
        base_currency: 'USD',
        commission: 0
      }

      const errorMessage = 'Failed to create item'
      mockApiClient.createPortfolioItem.mockRejectedValue(new Error(errorMessage))

      const { result } = renderHook(() => usePortfolioStore())

      await act(async () => {
        await result.current.createItem(newItem)
      })

      expect(result.current.items).toEqual([])
      expect(result.current.loading).toBe(false)
      expect(result.current.error).toBe(errorMessage)
    })
  })

  describe('updateItem', () => {
    it('should update portfolio item successfully', async () => {
      const existingItem = {
        id: 1,
        symbol: 'BTC',
        amount: 1.0,
        price_buy: 50000,
        base_currency: 'USD',
        commission: 0,
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-01T00:00:00Z'
      }

      const updatedItem = {
        ...existingItem,
        amount: 2.0,
        updated_at: '2023-01-01T01:00:00Z'
      }

      // Set initial state
      usePortfolioStore.setState({ items: [existingItem] })

      mockApiClient.updatePortfolioItem.mockResolvedValue(updatedItem)
      mockApiClient.getPortfolioSummary.mockResolvedValue({
        total_value: 100000,
        total_pnl: 0,
        total_pnl_percent: 0,
        currency: 'USD',
        item_count: 1
      })

      const { result } = renderHook(() => usePortfolioStore())

      await act(async () => {
        await result.current.updateItem(1, { amount: 2.0 })
      })

      expect(result.current.items[0]).toEqual(updatedItem)
      expect(result.current.loading).toBe(false)
      expect(result.current.error).toBeNull()
    })
  })

  describe('deleteItem', () => {
    it('should delete portfolio item successfully', async () => {
      const existingItem = {
        id: 1,
        symbol: 'BTC',
        amount: 1.0,
        price_buy: 50000,
        base_currency: 'USD',
        commission: 0,
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-01T00:00:00Z'
      }

      // Set initial state
      usePortfolioStore.setState({ items: [existingItem] })

      mockApiClient.deletePortfolioItem.mockResolvedValue({ message: 'Item deleted' })
      mockApiClient.getPortfolioSummary.mockResolvedValue({
        total_value: 0,
        total_pnl: 0,
        total_pnl_percent: 0,
        currency: 'USD',
        item_count: 0
      })

      const { result } = renderHook(() => usePortfolioStore())

      await act(async () => {
        await result.current.deleteItem(1)
      })

      expect(result.current.items).toEqual([])
      expect(result.current.loading).toBe(false)
      expect(result.current.error).toBeNull()
    })
  })

  describe('setCurrency', () => {
    it('should change currency and refresh data', async () => {
      const mockPortfolio = [
        {
          id: 1,
          symbol: 'BTC',
          amount: 1.5,
          price_buy: 50000,
          base_currency: 'EUR',
          commission: 0,
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z'
        }
      ]

      mockApiClient.getPortfolio.mockResolvedValue(mockPortfolio)
      mockApiClient.getPortfolioSummary.mockResolvedValue({
        total_value: 45000,
        total_pnl: 0,
        total_pnl_percent: 0,
        currency: 'EUR',
        item_count: 1
      })

      const { result } = renderHook(() => usePortfolioStore())

      await act(async () => {
        result.current.setCurrency('EUR')
      })

      expect(result.current.selectedCurrency).toBe('EUR')
      expect(mockApiClient.getPortfolio).toHaveBeenCalledWith('EUR')
      expect(mockApiClient.getPortfolioSummary).toHaveBeenCalledWith('EUR')
    })
  })

  describe('clearError', () => {
    it('should clear error state', () => {
      const { result } = renderHook(() => usePortfolioStore())

      // Set error state
      act(() => {
        usePortfolioStore.setState({ error: 'Some error' })
      })

      expect(result.current.error).toBe('Some error')

      // Clear error
      act(() => {
        result.current.clearError()
      })

      expect(result.current.error).toBeNull()
    })
  })
})
