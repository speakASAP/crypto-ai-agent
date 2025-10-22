/**
 * Unit tests for API Client
 */
import { apiClient } from '../lib/api'

// Mock fetch for testing
global.fetch = jest.fn()

const mockFetch = fetch as jest.MockedFunction<typeof fetch>

describe('API Client', () => {
  beforeEach(() => {
    mockFetch.mockClear()
  })

  describe('healthCheck', () => {
    it('should return health status', async () => {
      const mockResponse = {
        status: 'healthy',
        version: '2.0.0'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response)

      const result = await apiClient.healthCheck()

      expect(result).toEqual(mockResponse)
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/health',
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({
            'Content-Type': 'application/json'
          })
        })
      )
    })
  })

  describe('getPortfolio', () => {
    it('should fetch portfolio with default currency', async () => {
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

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPortfolio,
      } as Response)

      const result = await apiClient.getPortfolio()

      expect(result).toEqual(mockPortfolio)
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/portfolio/',
        expect.objectContaining({
          method: 'GET'
        })
      )
    })

    it('should fetch portfolio with specific currency', async () => {
      const mockPortfolio = [
        {
          id: 1,
          symbol: 'BTC',
          amount: 1.5,
          price_buy: 45000,
          base_currency: 'EUR',
          commission: 0,
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z'
        }
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPortfolio,
      } as Response)

      const result = await apiClient.getPortfolio('EUR')

      expect(result).toEqual(mockPortfolio)
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/portfolio/?currency=EUR',
        expect.objectContaining({
          method: 'GET'
        })
      )
    })
  })

  describe('createPortfolioItem', () => {
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

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => createdItem,
      } as Response)

      const result = await apiClient.createPortfolioItem(newItem)

      expect(result).toEqual(createdItem)
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/portfolio/',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(newItem)
        })
      )
    })
  })

  describe('updatePortfolioItem', () => {
    it('should update portfolio item successfully', async () => {
      const updateData = { amount: 2.0 }
      const updatedItem = {
        id: 1,
        symbol: 'BTC',
        amount: 2.0,
        price_buy: 50000,
        base_currency: 'USD',
        commission: 0,
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-01T01:00:00Z'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => updatedItem,
      } as Response)

      const result = await apiClient.updatePortfolioItem(1, updateData)

      expect(result).toEqual(updatedItem)
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/portfolio/1',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify(updateData)
        })
      )
    })
  })

  describe('deletePortfolioItem', () => {
    it('should delete portfolio item successfully', async () => {
      const deleteResponse = { message: 'Item deleted successfully' }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => deleteResponse,
      } as Response)

      const result = await apiClient.deletePortfolioItem(1)

      expect(result).toEqual(deleteResponse)
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/portfolio/1',
        expect.objectContaining({
          method: 'DELETE'
        })
      )
    })
  })

  describe('getPortfolioSummary', () => {
    it('should fetch portfolio summary', async () => {
      const mockSummary = {
        total_value: 100000,
        total_pnl: 5000,
        total_pnl_percent: 5.0,
        currency: 'USD',
        item_count: 2
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockSummary,
      } as Response)

      const result = await apiClient.getPortfolioSummary()

      expect(result).toEqual(mockSummary)
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/portfolio/summary',
        expect.objectContaining({
          method: 'GET'
        })
      )
    })
  })

  describe('getAlerts', () => {
    it('should fetch alerts with default active_only', async () => {
      const mockAlerts = [
        {
          id: 1,
          symbol: 'BTC',
          alert_type: 'ABOVE',
          threshold_price: 60000,
          is_active: true,
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z'
        }
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlerts,
      } as Response)

      const result = await apiClient.getAlerts()

      expect(result).toEqual(mockAlerts)
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/alerts/?active_only=true',
        expect.objectContaining({
          method: 'GET'
        })
      )
    })

    it('should fetch all alerts when active_only is false', async () => {
      const mockAlerts = [
        {
          id: 1,
          symbol: 'BTC',
          alert_type: 'ABOVE',
          threshold_price: 60000,
          is_active: true,
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z'
        },
        {
          id: 2,
          symbol: 'ETH',
          alert_type: 'BELOW',
          threshold_price: 3000,
          is_active: false,
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z'
        }
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlerts,
      } as Response)

      const result = await apiClient.getAlerts(false)

      expect(result).toEqual(mockAlerts)
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/alerts/?active_only=false',
        expect.objectContaining({
          method: 'GET'
        })
      )
    })
  })

  describe('createAlert', () => {
    it('should create alert successfully', async () => {
      const newAlert = {
        symbol: 'BTC',
        alert_type: 'ABOVE' as const,
        threshold_price: 60000,
        message: 'BTC price alert'
      }

      const createdAlert = {
        id: 1,
        ...newAlert,
        is_active: true,
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-01T00:00:00Z'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => createdAlert,
      } as Response)

      const result = await apiClient.createAlert(newAlert)

      expect(result).toEqual(createdAlert)
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/alerts/',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(newAlert)
        })
      )
    })
  })

  describe('getTrackedSymbols', () => {
    it('should fetch tracked symbols', async () => {
      const mockSymbols = [
        {
          symbol: 'BTC',
          is_active: true,
          created_at: '2023-01-01T00:00:00Z'
        },
        {
          symbol: 'ETH',
          is_active: true,
          created_at: '2023-01-01T00:00:00Z'
        }
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockSymbols,
      } as Response)

      const result = await apiClient.getTrackedSymbols()

      expect(result).toEqual(mockSymbols)
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/symbols/tracked?active_only=true',
        expect.objectContaining({
          method: 'GET'
        })
      )
    })
  })

  describe('getSymbolPrices', () => {
    it('should fetch symbol prices', async () => {
      const mockPrices = [
        {
          symbol: 'BTC',
          price: 50000,
          timestamp: '2023-01-01T00:00:00Z'
        },
        {
          symbol: 'ETH',
          price: 3000,
          timestamp: '2023-01-01T00:00:00Z'
        }
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPrices,
      } as Response)

      const result = await apiClient.getSymbolPrices(['BTC', 'ETH'])

      expect(result).toEqual(mockPrices)
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/symbols/prices?symbols=BTC,ETH',
        expect.objectContaining({
          method: 'GET'
        })
      )
    })
  })

  describe('Error Handling', () => {
    it('should handle network errors', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'))

      await expect(apiClient.getPortfolio()).rejects.toThrow('Network error - please check your connection')
    })

    it('should handle HTTP errors', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Internal server error' }),
      } as Response)

      await expect(apiClient.getPortfolio()).rejects.toThrow('Internal server error')
    })

    it('should handle timeout errors', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Request timeout'))

      await expect(apiClient.getPortfolio()).rejects.toThrow('Request timeout')
    })
  })
})
