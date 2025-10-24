'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { usePortfolioStore } from '@/stores/portfolioStore'
import { useAlertsStore } from '@/stores/alertsStore'
import { useSymbolsStore } from '@/stores/symbolsStore'
import { useAuthStore } from '@/stores/authStore'
import { useWebSocket } from '@/hooks/useWebSocket'
import { PortfolioModal } from '@/components/PortfolioModal'
import { AlertModal } from '@/components/AlertModal'
import { PortfolioItem, PortfolioCreate, PortfolioUpdate, PriceAlert, PriceAlertCreate, PriceAlertUpdate } from '@/types'
import { apiClient } from '@/lib/api'
import Link from 'next/link'

export default function Home() {
  const { items, summary, selectedCurrency, loading, fetchPortfolio, fetchSummary, setCurrency, createItem, updateItem, deleteItem } = usePortfolioStore()
  const { alerts, fetchAlerts, createAlert, updateAlert, deleteAlert } = useAlertsStore()
  const { trackedSymbols, fetchTrackedSymbols } = useSymbolsStore()
  const { user, logout, isHydrated, isAuthenticated } = useAuthStore()
  const { isConnected, subscribeToPrices, subscribeToAlerts, setExchangeRates: setWebSocketExchangeRates } = useWebSocket()
  
  // Modal states
  const [portfolioModalOpen, setPortfolioModalOpen] = useState(false)
  const [editingPortfolioItem, setEditingPortfolioItem] = useState<PortfolioItem | null>(null)
  const [alertModalOpen, setAlertModalOpen] = useState(false)
  const [editingAlert, setEditingAlert] = useState<PriceAlert | null>(null)
  const [presetAlertData, setPresetAlertData] = useState<{ 
    symbol: string; 
    currentPrice: number;
    portfolioItem?: {
      amount: number;
      price_buy: number;
      current_value?: number;
      pnl?: number;
      pnl_percent?: number;
    }
  } | null>(null)
  
  // Currency states
  const [exchangeRates, setExchangeRates] = useState<Record<string, number>>({})
  const [lastUpdated, setLastUpdated] = useState<string>('')
  const [lastUpdatedFormatted, setLastUpdatedFormatted] = useState<string>('')
  const [refreshingRates, setRefreshingRates] = useState(false)
  const [currencyChanging, setCurrencyChanging] = useState(false)
  
  // Crypto symbol states
  const [cryptoLastUpdated, setCryptoLastUpdated] = useState<string>('')
  const [cryptoLastUpdatedFormatted, setCryptoLastUpdatedFormatted] = useState<string>('')
  const [symbolTimestamps, setSymbolTimestamps] = useState<Record<string, string>>({})

  useEffect(() => {
    // Fetch initial data
    fetchPortfolio()
    fetchSummary()
    fetchAlerts()
    fetchTrackedSymbols()
    loadExchangeRates()
    loadCryptoTimestamps()
  }, [fetchPortfolio, fetchSummary, fetchAlerts, fetchTrackedSymbols])

  useEffect(() => {
    // Update WebSocket exchange rates whenever they change
    setWebSocketExchangeRates(exchangeRates)
  }, [exchangeRates, setWebSocketExchangeRates])

  const loadExchangeRates = async () => {
    try {
      const rates = await apiClient.getExchangeRates()
      setExchangeRates(rates.rates)
      setWebSocketExchangeRates(rates.rates) // Pass exchange rates to WebSocket hook for real-time price conversions
      setLastUpdated(rates.last_updated)
      setLastUpdatedFormatted(rates.last_updated_formatted || rates.last_updated)
    } catch (error) {
      console.error('Failed to load exchange rates:', error)
    }
  }

  const loadCryptoTimestamps = async () => {
    try {
      const timestamps = await apiClient.getSymbolLastUpdated()
      setCryptoLastUpdated(timestamps.last_bulk_update)
      setCryptoLastUpdatedFormatted(timestamps.last_bulk_update_formatted)
      setSymbolTimestamps(timestamps.symbol_timestamps)
    } catch (error) {
      console.error('Failed to load crypto timestamps:', error)
    }
  }

  const refreshExchangeRates = async () => {
    setRefreshingRates(true)
    try {
      const result = await apiClient.refreshExchangeRates()
      setLastUpdated(result.last_updated)
      // Reload exchange rates
      await loadExchangeRates()
      // Reload crypto timestamps
      await loadCryptoTimestamps()
      // Reload portfolio data with new rates
      fetchPortfolio()
      fetchSummary()
    } catch (error) {
      console.error('Failed to refresh exchange rates:', error)
    } finally {
      setRefreshingRates(false)
    }
  }

  useEffect(() => {
    // Subscribe to WebSocket updates
    if (isConnected) {
      subscribeToAlerts()
      
      // Subscribe to price updates for portfolio symbols
      if (items.length > 0) {
        const symbols = items.map(item => item.symbol)
        subscribeToPrices(symbols)
        console.log('📊 Subscribing to portfolio symbols:', symbols)
      }
      
      // Also subscribe to tracked symbols if available
      if (trackedSymbols.length > 0) {
        const symbols = trackedSymbols.map(s => s.symbol)
        subscribeToPrices(symbols)
        console.log('📊 Subscribing to tracked symbols:', symbols)
      }
    }
  }, [isConnected, items, trackedSymbols, subscribeToPrices, subscribeToAlerts])

  // Sync portfolio currency with user's preferred currency when user is available
  useEffect(() => {
    if (user && isHydrated && user.preferred_currency) {
      const { setCurrencyFromUserPreference } = usePortfolioStore.getState()
      setCurrencyFromUserPreference(user.preferred_currency as any)
    }
  }, [user, isHydrated])

  // Periodic refresh of timestamps every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      loadCryptoTimestamps()
    }, 30000) // 30 seconds

    return () => clearInterval(interval)
  }, [])

  // Currency to locale mapping for proper symbol display
  const currencyToLocale: Record<string, string> = {
    'USD': 'en-US',
    'EUR': 'de-DE', 
    'CZK': 'cs-CZ'
  }

  const formatCurrency = (amount: number) => {
    const locale = currencyToLocale[selectedCurrency] || 'en-US'
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: selectedCurrency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(amount)
  }

  const formatCurrencyWhole = (amount: number) => {
    const locale = currencyToLocale[selectedCurrency] || 'en-US'
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: selectedCurrency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount)
  }

  const formatPercent = (percent: number) => {
    return `${percent >= 0 ? '+' : ''}${percent.toFixed(2)}%`
  }

  const formatAmount = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(amount)
  }

  const getRelativeTime = (timestamp: string) => {
    if (!timestamp) return 'Unknown'
    
    try {
      const now = new Date()
      const time = new Date(timestamp)
      const diffMs = now.getTime() - time.getTime()
      const diffMinutes = Math.floor(diffMs / (1000 * 60))
      const diffSeconds = Math.floor(diffMs / 1000)
      
      if (diffSeconds < 60) {
        return `${diffSeconds}s ago`
      } else if (diffMinutes < 60) {
        return `${diffMinutes}m ago`
      } else if (diffMinutes < 1440) {
        const hours = Math.floor(diffMinutes / 60)
        return `${hours}h ago`
      } else {
        const days = Math.floor(diffMinutes / 1440)
        return `${days}d ago`
      }
    } catch (error) {
      return 'Invalid time'
    }
  }

  const getDataFreshness = (timestamp: string) => {
    if (!timestamp) return 'stale'
    
    try {
      const now = new Date()
      const time = new Date(timestamp)
      const diffMs = now.getTime() - time.getTime()
      const diffMinutes = Math.floor(diffMs / (1000 * 60))
      
      if (diffMinutes < 1) return 'fresh'
      if (diffMinutes < 5) return 'recent'
      return 'stale'
    } catch (error) {
      return 'stale'
    }
  }

  const handleCurrencyChange = async (newCurrency: string) => {
    if (currencyChanging || loading) return
    
    setCurrencyChanging(true)
    try {
      await setCurrency(newCurrency as any)
    } finally {
      setCurrencyChanging(false)
    }
  }

  // Portfolio handlers
  const handleAddPortfolioItem = () => {
    setEditingPortfolioItem(null)
    setPortfolioModalOpen(true)
  }

  const handleEditPortfolioItem = (item: PortfolioItem) => {
    setEditingPortfolioItem(item)
    setPortfolioModalOpen(true)
  }

  const handleDeletePortfolioItem = async (id: number) => {
    if (confirm('Are you sure you want to delete this portfolio item?')) {
      await deleteItem(id)
    }
  }

  const handleSavePortfolioItem = async (item: PortfolioCreate | PortfolioUpdate) => {
    if (editingPortfolioItem) {
      await updateItem(editingPortfolioItem.id, item as PortfolioUpdate)
    } else {
      await createItem(item as PortfolioCreate)
    }
  }

  // Alert handlers
  const handleAddAlert = () => {
    setEditingAlert(null)
    setAlertModalOpen(true)
  }

  const handleAddAlertForCoin = (item: PortfolioItem) => {
    setEditingAlert(null)
    setAlertModalOpen(true)
    // Store preset data in state to pass to modal
    setPresetAlertData({ 
      symbol: item.symbol, 
      currentPrice: item.current_price || 0,
      portfolioItem: {
        amount: item.amount,
        price_buy: item.price_buy,
        current_value: item.current_value,
        pnl: item.pnl,
        pnl_percent: item.pnl_percent
      }
    })
  }

  const handleEditAlert = (alert: PriceAlert) => {
    setEditingAlert(alert)
    setAlertModalOpen(true)
  }

  const handleDeleteAlert = async (id: number) => {
    if (confirm('Are you sure you want to delete this alert?')) {
      await deleteAlert(id)
    }
  }

  const handleSaveAlert = async (alert: PriceAlertCreate | PriceAlertUpdate) => {
    if (editingAlert) {
      await updateAlert(editingAlert.id, alert as PriceAlertUpdate)
    } else {
      await createAlert(alert as PriceAlertCreate)
    }
  }

  // Debug authentication state
  console.log('🏠 Main page auth state:', {
    isHydrated,
    isAuthenticated,
    hasUser: !!user,
    hasAccessToken: !!useAuthStore.getState().accessToken
  })

  // Show loading state until hydrated
  if (!isHydrated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-2 text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    console.log('🚫 Main page: User not authenticated, showing login redirect')
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Authentication Required</h1>
          <p className="text-gray-600 mb-6">Please log in to access your portfolio.</p>
          <Link href="/login">
            <Button>Go to Login</Button>
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold">Crypto AI Agent v2.0</h1>
          <p className="text-gray-600 mt-1">
            {user 
              ? `Welcome back, ${user.full_name || user.username}!`
              : 'Welcome to Crypto AI Agent!'
            }
          </p>
        </div>
        <div className="flex items-center space-x-4">
          {user ? (
            <>
              <Link href="/profile">
                <Button variant="outline">
                  Profile
                </Button>
              </Link>
              <Button variant="outline" onClick={logout}>
                Logout
              </Button>
            </>
          ) : (
            <div className="flex items-center space-x-4">
              <Link href="/login">
                <Button variant="outline">
                  Login
                </Button>
              </Link>
              <Link href="/register">
                <Button variant="outline">
                  Register
                </Button>
              </Link>
            </div>
          )}
        </div>
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <span className="text-sm text-muted-foreground">Currency:</span>
            <div className="relative">
              <select 
                value={selectedCurrency} 
                onChange={(e) => handleCurrencyChange(e.target.value)}
                className="px-3 py-1 border rounded transition-all duration-300 ease-in-out disabled:opacity-50"
                disabled={loading || currencyChanging}
              >
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="CZK">CZK</option>
              </select>
              {(loading || currencyChanging) && (
                <div className="absolute -right-6 top-1/2 transform -translate-y-1/2">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                </div>
              )}
            </div>
            <Button 
              onClick={refreshExchangeRates}
              disabled={refreshingRates}
              size="sm"
              variant="outline"
            >
              {refreshingRates ? 'Refreshing...' : '🔄'}
            </Button>
          </div>
          <div className="flex items-center space-x-2">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-sm text-muted-foreground">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
          <div className="flex flex-col space-y-1">
            {lastUpdatedFormatted && (
              <div className="text-xs text-muted-foreground">
                <div className="flex items-center space-x-1">
                  <div className={`w-1.5 h-1.5 rounded-full ${
                    getDataFreshness(lastUpdated) === 'fresh' ? 'bg-green-500' : 
                    getDataFreshness(lastUpdated) === 'recent' ? 'bg-yellow-500' : 'bg-red-500'
                  }`} />
                  <span>Currency Rates: {lastUpdatedFormatted}</span>
                </div>
                <div className="text-xs text-gray-500 ml-2">
                  {getRelativeTime(lastUpdated)}
                </div>
              </div>
            )}
            {cryptoLastUpdatedFormatted && (
              <div className="text-xs text-muted-foreground">
                <div className="flex items-center space-x-1">
                  <div className={`w-1.5 h-1.5 rounded-full ${
                    getDataFreshness(cryptoLastUpdated) === 'fresh' ? 'bg-green-500' : 
                    getDataFreshness(cryptoLastUpdated) === 'recent' ? 'bg-yellow-500' : 'bg-red-500'
                  }`} />
                  <span>Crypto Prices: {cryptoLastUpdatedFormatted}</span>
                </div>
                <div className="text-xs text-gray-500 ml-2">
                  {getRelativeTime(cryptoLastUpdated)}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Value</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="text-2xl font-bold transition-all duration-300 ease-in-out">
                {(loading || currencyChanging) ? (
                  <span className="animate-pulse">Loading...</span>
                ) : summary ? formatCurrencyWhole(summary.total_value) : 'Loading...'}
              </div>
              <div className="text-lg text-blue-600 font-medium transition-all duration-300 ease-in-out">
                {(loading || currencyChanging) ? (
                  <span className="animate-pulse">Loading...</span>
                ) : summary ? formatCurrencyWhole(summary.total_invested) : 'Loading...'}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total P&L</CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold transition-all duration-300 ease-in-out ${summary && summary.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {(loading || currencyChanging) ? (
                <span className="animate-pulse">Loading...</span>
              ) : summary ? formatCurrencyWhole(summary.total_pnl) : 'Loading...'}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">P&L %</CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold transition-all duration-300 ease-in-out ${summary && summary.total_pnl_percent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {(loading || currencyChanging) ? (
                <span className="animate-pulse">Loading...</span>
              ) : summary ? formatPercent(summary.total_pnl_percent) : 'Loading...'}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Items</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {summary ? summary.item_count : 'Loading...'}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Portfolio Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Portfolio</CardTitle>
              <CardDescription>Your cryptocurrency holdings</CardDescription>
            </div>
            <Button onClick={handleAddPortfolioItem}>
              Add New Item
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8">Loading portfolio...</div>
          ) : items.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No portfolio items found. Add some cryptocurrencies to get started.
            </div>
          ) : (
            <div className="space-y-4">
              {items.map((item) => (
                <div key={item.id} className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="flex items-center space-x-4">
                    <div className="font-semibold">{item.symbol}</div>
                    {item.total_investment_text && (
                      <div className="text-sm font-medium text-blue-600 bg-blue-50 px-2 py-1 rounded">
                        {item.total_investment_text}
                      </div>
                    )}
                    <div className="text-sm text-muted-foreground">
                      {formatAmount(item.amount)} @ {formatCurrency(item.price_buy)}
                    </div>
                    {item.source && (
                      <div className="text-sm text-muted-foreground">
                        via {item.source}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center space-x-4">
                    <div className="text-right">
                      <div className="text-sm text-muted-foreground transition-all duration-300 ease-in-out">
                        {(loading || currencyChanging) ? (
                          <span className="animate-pulse">Loading...</span>
                        ) : item.current_price ? formatCurrency(item.current_price) : 'N/A'}
                      </div>
                    </div>
                    {item.current_value && (
                      <div className="text-right">
                        <div className={`text-sm font-medium px-2 py-1 rounded transition-all duration-300 ease-in-out ${
                          item.current_value >= (item.amount * item.price_buy) + item.commission
                            ? 'text-green-600 bg-green-50'
                            : 'text-red-600 bg-red-50'
                        }`}>
                          {(loading || currencyChanging) ? (
                            <span className="animate-pulse">Loading...</span>
                          ) : formatCurrency(item.current_value)}
                        </div>
                        {item.pnl !== undefined && (
                          <div className={`text-sm transition-all duration-300 ease-in-out ${item.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {(loading || currencyChanging) ? (
                              <span className="animate-pulse">Loading...</span>
                            ) : (
                              <>
                                {formatCurrency(item.pnl)} ({formatPercent(item.pnl_percent || 0)})
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                    <div className="flex items-center space-x-2">
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => handleAddAlertForCoin(item)}
                        className="text-blue-600 hover:text-blue-700"
                        disabled={!item.current_price}
                      >
                        Set Alert
                      </Button>
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => handleEditPortfolioItem(item)}
                      >
                        Edit
                      </Button>
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => handleDeletePortfolioItem(item.id)}
                        className="text-red-600 hover:text-red-700"
                      >
                        Delete
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Alerts */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Price Alerts</CardTitle>
              <CardDescription>Active price notifications</CardDescription>
            </div>
            <Button onClick={handleAddAlert}>
              Create Alert
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {alerts.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No active alerts. Create some price alerts to get notified.
            </div>
          ) : (
            <div className="space-y-2">
              {alerts.map((alert) => (
                <div key={alert.id} className="flex items-center justify-between p-3 border rounded">
                  <div>
                    <span className="font-medium">{alert.symbol}</span>
                    <span className="ml-2 text-sm text-muted-foreground">
                      {alert.alert_type} {formatCurrency(alert.threshold_price)}
                    </span>
                    {alert.message && (
                      <div className="text-sm text-muted-foreground mt-1">
                        {alert.message}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className={`px-2 py-1 text-xs rounded ${
                      alert.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                    }`}>
                      {alert.is_active ? 'Active' : 'Inactive'}
                    </span>
                    <div className="flex items-center space-x-1">
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => handleEditAlert(alert)}
                      >
                        Edit
                      </Button>
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => handleDeleteAlert(alert.id)}
                        className="text-red-600 hover:text-red-700"
                      >
                        Delete
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Modals */}
      <PortfolioModal
        isOpen={portfolioModalOpen}
        onClose={() => setPortfolioModalOpen(false)}
        onSave={handleSavePortfolioItem}
        item={editingPortfolioItem}
        selectedCurrency={selectedCurrency}
      />

      <AlertModal
        isOpen={alertModalOpen}
        onClose={() => {
          setAlertModalOpen(false)
          setPresetAlertData(null)
        }}
        onSave={handleSaveAlert}
        alert={editingAlert}
        presetSymbol={presetAlertData?.symbol}
        currentPrice={presetAlertData?.currentPrice}
        selectedCurrency={selectedCurrency}
        portfolioItem={presetAlertData?.portfolioItem}
      />
    </div>
  )
}


