import axios, { AxiosInstance, AxiosResponse } from 'axios'
import { 
  PortfolioItem, 
  PortfolioCreate, 
  PortfolioUpdate, 
  PortfolioSummary,
  PriceAlert,
  PriceAlertCreate,
  PriceAlertUpdate,
  AlertHistory,
  TrackedSymbol,
  TrackedSymbolCreate,
  TrackedSymbolUpdate,
  CryptoSymbol,
  CryptoSymbolCreate,
  CryptoSymbolUpdate,
  SymbolPrice,
  ApiError
} from '@/types'
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
import { useAuthStore } from '@/stores/authStore'
import { logger } from '@/lib/logger'

class ApiClient {
  public client: AxiosInstance
  private isRefreshing = false
  private refreshPromise: Promise<any> | null = null

  constructor() {
    this.client = axios.create({
      baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
      timeout: 30000, // Increased to 30 seconds to prevent timeout errors
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        // Only add auth header on client side and when hydrated
        if (typeof window !== 'undefined') {
          const authState = useAuthStore.getState()
          
          logger.debug('🔍 API Request - Auth state:', {
            isHydrated: authState.isHydrated,
            hasAccessToken: !!authState.accessToken,
            isAuthenticated: authState.isAuthenticated,
            url: config.url
          })
          
          // Only proceed if store is hydrated
          if (authState.isHydrated && authState.accessToken) {
            config.headers.Authorization = `Bearer ${authState.accessToken}`
            logger.debug('✅ Added auth header to request:', config.url)
          } else if (authState.isHydrated) {
            logger.debug('❌ No access token available for request:', config.url)
          } else {
            logger.debug('⏳ Auth store not hydrated yet for request:', config.url)
          }
        }
        
        logger.debug(`🚀 ${config.method?.toUpperCase()} ${config.url}`)
        return config
      },
      (error) => {
        logger.error('❌ Request error:', error)
        return Promise.reject(error)
      }
    )

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => {
        logger.debug(`✅ ${response.status} ${response.config.url}`)
        return response
      },
      async (error) => {
        logger.error('❌ Response error:', error.response?.data || error.message)
        
        // Handle 401 errors (token expired)
        if (error.response?.status === 401) {
          // Only handle refresh on client side and when hydrated
          if (typeof window !== 'undefined') {
            const authState = useAuthStore.getState()
            logger.debug('🔄 401 error - auth state:', { 
              hasRefreshToken: !!authState.refreshToken, 
              isAuthenticated: authState.isAuthenticated,
              isHydrated: authState.isHydrated,
              url: error.config?.url 
            })
            
            if (authState.isHydrated && authState.refreshToken && !this.isRefreshing) {
              this.isRefreshing = true
              this.refreshPromise = this.performTokenRefresh(error.config)
            } else if (this.isRefreshing && this.refreshPromise) {
              // If already refreshing, wait for the existing refresh to complete
              return this.refreshPromise
            } else {
              logger.debug('🔄 No refresh token, not hydrated, or already refreshing')
              // If no refresh token available, logout immediately
              if (authState.isHydrated) {
                authState.logout()
              }
              return Promise.reject(this.handleError(error))
            }
          }
        }
        
        return Promise.reject(this.handleError(error))
      }
    )
  }

  private async performTokenRefresh(originalConfig: any): Promise<any> {
    try {
      logger.debug('🔄 Attempting token refresh...')
      const authState = useAuthStore.getState()
      await authState.refreshAccessToken()
      logger.debug('✅ Token refresh successful')
      
      // Retry the original request
      const newAuthState = useAuthStore.getState()
      originalConfig.headers.Authorization = `Bearer ${newAuthState.accessToken}`
      return this.client(originalConfig)
    } catch (refreshError) {
      logger.debug('🔄 Token refresh failed:', refreshError instanceof Error ? refreshError.message : 'Unknown error')
      // Immediately logout on refresh failure
      const authState = useAuthStore.getState()
      authState.logout()
      return Promise.reject(this.handleError(refreshError))
    } finally {
      this.isRefreshing = false
      this.refreshPromise = null
    }
  }

  private handleError(error: any): ApiError {
    if (error.response) {
      return {
        message: error.response.data?.detail || error.response.data?.message || 'An error occurred',
        status: error.response.status,
        details: error.response.data
      }
    } else if (error.request) {
      return {
        message: 'Network error - please check your connection',
        status: 0,
        details: error.request
      }
    } else {
      return {
        message: error.message || 'An unexpected error occurred',
        status: 0,
        details: error
      }
    }
  }

  // Health check
  async healthCheck(): Promise<{ status: string; version: string }> {
    const response = await this.client.get('/health')
    return response.data
  }

  // Authentication endpoints
  async register(userData: UserRegister): Promise<TokenResponse> {
    const response = await this.client.post('/api/auth/register', userData)
    return response.data
  }

  async login(credentials: UserLogin): Promise<TokenResponse> {
    const response = await this.client.post('/api/auth/login', credentials)
    return response.data
  }

  async refreshToken(refreshToken: string): Promise<TokenResponse> {
    const response = await this.client.post('/api/auth/refresh', null, {
      params: { refresh_token: refreshToken }
    })
    return response.data
  }

  async getCurrentUser(): Promise<User> {
    const response = await this.client.get('/api/auth/me')
    return response.data
  }

  async requestPasswordReset(email: string): Promise<{ message: string }> {
    const response = await this.client.post('/api/auth/password-reset-request', { email })
    return response.data
  }

  async confirmPasswordReset(token: string, newPassword: string): Promise<{ message: string }> {
    const response = await this.client.post('/api/auth/password-reset-confirm', { 
      token, 
      new_password: newPassword 
    })
    return response.data
  }

  async updateProfile(updateData: UserProfileUpdate): Promise<User> {
    const response = await this.client.put('/api/auth/profile', updateData)
    return response.data
  }

  async changePassword(passwordChange: PasswordChange): Promise<{ message: string }> {
    const response = await this.client.post('/api/auth/change-password', passwordChange)
    return response.data
  }

  async deleteAccount(confirmationText: string): Promise<{ message: string }> {
    const response = await this.client.delete('/api/auth/delete-account', {
      data: { confirmation_text: confirmationText }
    })
    return response.data
  }

  async testTelegramConnection(): Promise<{ message: string; success: boolean }> {
    const response = await this.client.post('/api/auth/test-telegram')
    return response.data
  }

  async saveBinanceCredentials(apiKey: string, apiSecret: string): Promise<any> {
    const response = await this.client.post('/api/auth/binance-credentials', {
      api_key: apiKey,
      api_secret: apiSecret
    })
    return response.data
  }

  async testBinanceConnection(): Promise<any> {
    const response = await this.client.post('/api/auth/test-binance-connection')
    return response.data
  }

  async deleteBinanceCredentials(): Promise<{ message: string }> {
    const response = await this.client.delete('/api/auth/binance-credentials')
    return response.data
  }

  async getBinanceCredentials(): Promise<any> {
    const response = await this.client.get('/api/auth/binance-credentials')
    return response.data
  }

  // Bitfinex credential management
  async saveBitfinexCredentials(apiKey: string, apiSecret: string): Promise<any> {
    const response = await this.client.post('/api/auth/bitfinex-credentials', {
      api_key: apiKey,
      api_secret: apiSecret
    })
    return response.data
  }

  async testBitfinexConnection(): Promise<any> {
    const response = await this.client.post('/api/auth/test-bitfinex-connection')
    return response.data
  }

  async deleteBitfinexCredentials(): Promise<{ message: string }> {
    const response = await this.client.delete('/api/auth/bitfinex-credentials')
    return response.data
  }

  async getBitfinexCredentials(): Promise<any> {
    const response = await this.client.get('/api/auth/bitfinex-credentials')
    return response.data
  }

  // Portfolio endpoints
  async getPortfolio(currency?: string): Promise<PortfolioItem[]> {
    const params = currency ? { currency } : {}
    const response = await this.client.get('/api/portfolio/', { params })
    return response.data
  }

  async createPortfolioItem(item: PortfolioCreate): Promise<PortfolioItem> {
    const response = await this.client.post('/api/portfolio/', item)
    return response.data
  }

  async updatePortfolioItem(id: number, item: PortfolioUpdate): Promise<PortfolioItem> {
    const response = await this.client.put(`/api/portfolio/${id}`, item)
    return response.data
  }

  async deletePortfolioItem(id: number): Promise<{ message: string }> {
    const response = await this.client.delete(`/api/portfolio/${id}`)
    return response.data
  }

  async getPortfolioSummary(currency?: string): Promise<PortfolioSummary> {
    const params = currency ? { currency } : {}
    const response = await this.client.get('/api/portfolio/summary', { params })
    return response.data
  }

  // Alerts endpoints
  async getAlerts(activeOnly = true): Promise<PriceAlert[]> {
    const params = { active_only: activeOnly }
    const response = await this.client.get('/api/alerts/', { params })
    return response.data
  }

  async createAlert(alert: PriceAlertCreate): Promise<PriceAlert> {
    const response = await this.client.post('/api/alerts/', alert)
    return response.data
  }

  async updateAlert(id: number, alert: PriceAlertUpdate): Promise<PriceAlert> {
    const response = await this.client.put(`/api/alerts/${id}`, alert)
    return response.data
  }

  async deleteAlert(id: number): Promise<{ message: string }> {
    const response = await this.client.delete(`/api/alerts/${id}`)
    return response.data
  }

  async getAlertHistory(limit = 100): Promise<AlertHistory[]> {
    const params = { limit }
    const response = await this.client.get('/api/alerts/history', { params })
    return response.data
  }

  async triggerAlert(id: number, currentPrice: number): Promise<{ message: string; alert_id: number }> {
    const response = await this.client.post(`/api/alerts/${id}/trigger`, {
      current_price: currentPrice
    })
    return response.data
  }

  // Symbols endpoints
  async getTrackedSymbols(activeOnly = true): Promise<TrackedSymbol[]> {
    const params = { active_only: activeOnly }
    const response = await this.client.get('/api/symbols/tracked', { params })
    return response.data
  }

  async addTrackedSymbol(symbol: TrackedSymbolCreate): Promise<TrackedSymbol> {
    const response = await this.client.post('/api/symbols/tracked', symbol)
    return response.data
  }

  async updateTrackedSymbol(symbol: string, update: TrackedSymbolUpdate): Promise<TrackedSymbol> {
    const response = await this.client.put(`/api/symbols/tracked/${symbol}`, update)
    return response.data
  }

  async removeTrackedSymbol(symbol: string): Promise<{ message: string }> {
    const response = await this.client.delete(`/api/symbols/tracked/${symbol}`)
    return response.data
  }


  async addCryptoSymbol(symbol: CryptoSymbolCreate): Promise<CryptoSymbol> {
    const response = await this.client.post('/api/symbols/crypto', symbol)
    return response.data
  }

  async updateCryptoSymbol(id: number, symbol: CryptoSymbolUpdate): Promise<CryptoSymbol> {
    const response = await this.client.put(`/api/symbols/crypto/${id}`, symbol)
    return response.data
  }

  async getSymbolPrices(symbols: string[]): Promise<SymbolPrice[]> {
    const params = { symbols: symbols.join(',') }
    const response = await this.client.get('/api/symbols/prices', { params })
    return response.data
  }

  async getSymbolPrice(symbol: string): Promise<{ symbol: string; price: number; timestamp: string }> {
    const response = await this.client.get(`/api/symbols/${symbol}/price`)
    return response.data
  }

  // Currency endpoints
  async refreshExchangeRates(): Promise<{ message: string; rates_count: number; last_updated: string }> {
    const response = await this.client.post('/api/currency/refresh')
    return response.data
  }

  async getExchangeRates(): Promise<{ 
    base_currency: string; 
    rates: Record<string, number>; 
    last_updated: string;
    last_updated_timestamp: string;
    last_updated_formatted: string;
  }> {
    const response = await this.client.get('/api/currency/rates')
    return response.data
  }

  async getSymbolLastUpdated(): Promise<{
    last_bulk_update: string;
    last_bulk_update_formatted: string;
    symbol_timestamps: Record<string, string>;
  }> {
    const response = await this.client.get('/api/symbols/last-updated')
    return response.data
  }

  async refreshCryptoPrices(): Promise<{ 
    message: string; 
    symbols_count: number; 
    symbols: string[];
    last_updated: string;
  }> {
    const response = await this.client.post('/api/crypto/refresh')
    return response.data
  }

  // Crypto symbols endpoints
  async getCryptoSymbols(limit: number = 500): Promise<CryptoSymbol[]> {
    const response = await this.client.get(`/api/crypto-symbols?limit=${limit}`)
    return response.data
  }

  async searchCryptoSymbols(query: string, limit: number = 50): Promise<CryptoSymbol[]> {
    const response = await this.client.get(`/api/crypto-symbols/search?q=${encodeURIComponent(query)}&limit=${limit}`)
    return response.data
  }

  async refreshCryptoSymbols(): Promise<{ 
    message: string; 
    count: number; 
    last_updated: string;
  }> {
    const response = await this.client.post('/api/crypto-symbols/refresh')
    return response.data
  }

  // Binance import endpoints
  async importBinancePortfolio(): Promise<{ 
    success: boolean;
    message: string;
    items_imported: number;
    portfolio_items?: any[];
    error?: string;
  }> {
    // Increase timeout to 120 seconds for Binance import (can take a while)
    const response = await this.client.post('/api/import/binance/execute', {}, {
      timeout: 120000
    })
    return response.data
  }

  // Bitfinex import endpoints
  async importBitfinexPortfolio(): Promise<{ 
    success: boolean;
    message: string;
    items_imported: number;
    portfolio_items?: any[];
    error?: string;
  }> {
    // Increase timeout to 120 seconds for Bitfinex import (can take a while)
    const response = await this.client.post('/api/import/bitfinex/execute', {}, {
      timeout: 120000
    })
    return response.data
  }

  // CSV import endpoints
  async uploadCSV(file: File): Promise<{ 
    success: boolean;
    message: string;
    detected_exchange?: string;
    preview_data: any[];
    total_rows: number;
    aggregated_items: any[];
    errors: string[];
    items_to_add?: any[];
    items_to_update?: any[];
    items_to_delete?: any[];
  }> {
    const formData = new FormData()
    formData.append('file', file)
    
    const response = await this.client.post('/api/import/csv/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      timeout: 60000
    })
    return response.data
  }

  async executeCSVImport(file: File, exchange: string): Promise<{ 
    success: boolean;
    message: string;
    items_imported: number;
    total_found: number;
  }> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('exchange', exchange)
    
    logger.debug('📤 Executing CSV import:', { exchange, fileName: file.name, fileSize: file.size })
    
    const response = await this.client.post('/api/import/csv/execute', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      timeout: 120000
    })
    
    logger.debug('✅ CSV import response:', response.data)
    return response.data
  }

  async getCSVTemplates(): Promise<{ templates: any[] }> {
    const response = await this.client.get('/api/import/csv/templates')
    return response.data
  }

}

// Create singleton instance
export const apiClient = new ApiClient()
export default apiClient
