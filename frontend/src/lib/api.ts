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
  ApiError,
  PredictionResponse,
  NewsAnalysis,
  ChartData,
  PerformanceStats
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
          
          // Skip interceptor if token is already set (for retry after refresh)
          if (config._skipAuthInterceptor && config.headers?.Authorization) {
            logger.debug('⏭️ Skipping interceptor - token already set for retry:', config.url)
            delete config._skipAuthInterceptor // Clean up flag
            return config
          }
          
          // Add token if available (don't require hydration for immediate use after login)
          // Also check if token is being passed directly in config (for retry after refresh)
          const authHeader = config.headers?.Authorization
          const tokenFromConfig = typeof authHeader === 'string' ? authHeader.replace('Bearer ', '') : null
          const tokenToUse = tokenFromConfig || authState.accessToken
          
          if (tokenToUse) {
            config.headers.Authorization = `Bearer ${tokenToUse}`
            logger.debug('✅ Added auth header to request:', config.url)
          } else if (authState.isHydrated) {
            logger.debug('❌ No access token available for request:', config.url)
          } else {
            logger.debug('⏳ Auth store not hydrated yet, but checking for token:', config.url)
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
        // Handle 503 Service Unavailable errors with retry logic
        if (error.response?.status === 503) {
          const config = error.config || {}
          const retryCount = config.__retryCount || 0
          const maxRetries = 3
          const initialDelay = 2000 // 2 seconds
          
          // Log 503 errors - these indicate real service issues that need attention
          logger.warn(`⚠️ Service Unavailable (503) for ${config.url}, attempt ${retryCount + 1}/${maxRetries + 1}`)
          
          if (retryCount < maxRetries) {
            // Calculate exponential backoff delay: 2s, 4s, 8s
            const delay = initialDelay * Math.pow(2, retryCount)
            
            // Update retry count in config
            config.__retryCount = retryCount + 1
            
            // Wait before retrying
            await new Promise(resolve => setTimeout(resolve, delay))
            
            // Retry the request
            logger.debug(`🔄 Retrying request for ${config.url} after ${delay}ms delay`)
            return this.client(config)
          } else {
            // Max retries exceeded - log error
            logger.error(`❌ Service Unavailable (503) for ${config.url} after ${maxRetries} retries`)
            return Promise.reject(this.handleError(error))
          }
        }
        
        // Handle 401 errors (token expired)
        if (error.response?.status === 401) {
          // Only handle refresh on client side
          if (typeof window !== 'undefined') {
            const authState = useAuthStore.getState()
            
            // Prevent infinite loop - if this is a retry after refresh, don't refresh again
            if (error.config?._skipAuthInterceptor) {
              logger.debug('🔄 401 on retry after refresh - token may be invalid, logging out')
              authState.logout()
              return Promise.reject(this.handleError(error))
            }
            
            logger.debug('🔄 401 error - auth state:', { 
              hasRefreshToken: !!authState.refreshToken, 
              isAuthenticated: authState.isAuthenticated,
              isHydrated: authState.isHydrated,
              url: error.config?.url 
            })
            
            if (authState.refreshToken && !this.isRefreshing) {
              this.isRefreshing = true
              this.refreshPromise = this.performTokenRefresh(error.config)
              return this.refreshPromise
            } else if (this.isRefreshing && this.refreshPromise) {
              // If already refreshing, wait for the existing refresh to complete
              return this.refreshPromise
            } else {
              logger.debug('🔄 No refresh token or already refreshing')
              // If no refresh token available, logout immediately
              if (authState.isHydrated) {
                authState.logout()
              }
              return Promise.reject(this.handleError(error))
            }
          }
        }
        
        // Handle 404 errors for chart endpoints - suppress console errors
        if (error.response?.status === 404) {
          const url = error.config?.url || ''
          // Suppress console errors for chart endpoints (404 is expected when data doesn't exist)
          if (url.includes('/charts/mini/') || url.includes('/charts/history/')) {
            logger.debug(`⚠️ Chart data not found (404) for ${url}`)
            // Don't log to console, just return error gracefully
            return Promise.reject(this.handleError(error))
          }
        }
        
        // For other errors, log normally
        if (error.response?.status !== 503 && error.response?.status !== 404) {
          logger.error('❌ Response error:', error.response?.data || error.message)
        }
        
        return Promise.reject(this.handleError(error))
      }
    )
  }

  private async performTokenRefresh(originalConfig: any): Promise<any> {
    try {
      logger.debug('🔄 Attempting token refresh...')
      const authState = useAuthStore.getState()
      
      // Call refresh token API directly (bypass interceptor to avoid circular 401)
      const refreshResponse = await this.client.post('/api/auth/refresh', null, {
        params: { refresh_token: authState.refreshToken },
        headers: {} // No auth header for refresh request
      })
      
      const tokenData = refreshResponse.data
      
      if (!tokenData.access_token) {
        throw new Error('No access token in refresh response')
      }
      
      // Update store directly with new tokens
      useAuthStore.setState({
        accessToken: tokenData.access_token,
        refreshToken: tokenData.refresh_token,
        user: tokenData.user,
        isAuthenticated: true,
      })
      
      logger.debug('✅ Token refresh successful, new token:', tokenData.access_token.substring(0, 20) + '...')
      
      // Wait a bit for store to update
      await new Promise(resolve => setTimeout(resolve, 150))
      
      // Create a new config object with new token - mark it to skip interceptor token addition
      const retryConfig = {
        ...originalConfig,
        _skipAuthInterceptor: true, // Flag to skip interceptor token addition
        headers: {
          ...originalConfig.headers,
          Authorization: `Bearer ${tokenData.access_token}` // Use token directly from response
        }
      }
      
      logger.debug('🔄 Retrying request with new token:', retryConfig.url)
      
      // Retry the request - it will go through interceptor but will use the token we set
      return this.client(retryConfig)
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
      let message = 'An error occurred'
      const detail = error.response.data?.detail
      
      // Handle validation errors (422) - detail is an array
      if (Array.isArray(detail) && detail.length > 0) {
        const firstError = detail[0]
        if (firstError.msg) {
          message = firstError.msg
        } else if (typeof firstError === 'string') {
          message = firstError
        }
      } else if (typeof detail === 'string') {
        message = detail
      } else if (error.response.data?.message) {
        message = error.response.data.message
      }
      
      return {
        message,
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
    const response = await this.client.get('/api/health')
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

  async getCurrentUser(accessToken?: string): Promise<User> {
    const config: any = {}
    if (accessToken) {
      config.headers = { Authorization: `Bearer ${accessToken}` }
    }
    const response = await this.client.get('/api/auth/me', config)
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
    items_with_issues?: Array<{
      symbol: string;
      amount: number;
      issues: string[];
      warnings: string[];
      price_buy?: number;
      price_buy_usd?: number;
      purchase_date?: string;
    }>;
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
    items_with_issues?: Array<{
      symbol: string;
      amount: number;
      issues: string[];
      warnings: string[];
      price_buy?: number;
      price_buy_usd?: number;
      purchase_date?: string;
    }>;
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
    items_with_issues?: Array<{
      symbol: string;
      amount: number;
      issues: string[];
      warnings: string[];
      price_buy?: number;
      price_buy_usd?: number;
      purchase_date?: string;
    }>;
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

  // AI Advisor endpoints
  async getAIPredictions(symbol: string): Promise<PredictionResponse> {
    const response = await this.client.get(`/api/ai-advisor/predictions/${symbol}`)
    return response.data
  }

  async getPortfolioPredictions(): Promise<Record<string, PredictionResponse>> {
    const response = await this.client.get('/api/ai-advisor/predictions/portfolio')
    return response.data
  }

  async generatePredictions(symbol: string): Promise<PredictionResponse> {
    const response = await this.client.post(`/api/ai-advisor/generate/${symbol}`)
    return response.data
  }

  async getAIPerformance(symbol?: string, modelName?: string): Promise<PerformanceStats> {
    let url = '/api/ai-advisor/performance'
    if (symbol) {
      url += `/${symbol}`
    } else if (modelName) {
      url += `?model_name=${encodeURIComponent(modelName)}`
    }
    const response = await this.client.get(url)
    return response.data
  }

  async getAIPerformanceByModel(): Promise<PerformanceStats> {
    const response = await this.client.get('/api/ai-advisor/performance/by-model')
    return response.data
  }

  async getAINews(symbol: string, days: number = 7): Promise<NewsAnalysis[]> {
    const response = await this.client.get(`/api/ai-advisor/news/${symbol}?days=${days}`)
    return response.data
  }

  // Charts endpoints
  async getPriceHistory(symbol: string, days: number = 365): Promise<ChartData> {
    const response = await this.client.get(`/api/charts/history/${symbol}?days=${days}`)
    return response.data
  }

  async triggerChartFetch(symbols: string[]): Promise<{ message: string; symbols: string[] }> {
    const response = await this.client.post('/api/charts/fetch', symbols)
    return response.data
  }

  async getMiniChart(symbol: string, days: number = 7): Promise<ChartData> {
    const response = await this.client.get(`/api/charts/mini/${symbol}?days=${days}`)
    return response.data
  }

}

// Create singleton instance
export const apiClient = new ApiClient()
export default apiClient
