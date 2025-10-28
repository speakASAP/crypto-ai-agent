'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { usePortfolioStore } from '@/stores/portfolioStore'
import { useAlertsStore } from '@/stores/alertsStore'
import { useSymbolsStore } from '@/stores/symbolsStore'
import { useAuthStore } from '@/stores/authStore'
import { useWebSocket } from '@/hooks/useWebSocket'
import { PortfolioModal } from '@/components/PortfolioModal'
import { AlertModal } from '@/components/AlertModal'
import { PortfolioItem, PortfolioCreate, PortfolioUpdate, PriceAlert, PriceAlertCreate, PriceAlertUpdate } from '@/types'
import { apiClient } from '@/lib/api'
import { getRelativeTime, getDataFreshness, getFreshnessColorClass, getTimestampDisplay } from '@/lib/timeUtils'
import { refreshAllData } from '@/lib/refreshUtils'
import { formatCurrency, formatCurrencyWhole, formatPercent, formatCryptoAmount, formatInvestmentText, Currency } from '@/lib/currencyUtils'
import Link from 'next/link'
import { User, LogOut } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'

export default function Home() {
  const router = useRouter()
  const { items, summary, selectedCurrency, loading, fetchPortfolio, fetchSummary, setCurrency, createItem, updateItem, deleteItem, viewMode, sort, filters, setViewMode, setSort, setFilters, loadPreferencesFromUser } = usePortfolioStore()
  const { alerts, fetchAlerts, createAlert, updateAlert, deleteAlert } = useAlertsStore()
  const { trackedSymbols, fetchTrackedSymbols } = useSymbolsStore()
  const { user, logout, isHydrated, isAuthenticated } = useAuthStore()
  const { isConnected, subscribeToPrices, subscribeToAlerts, setExchangeRates: setWebSocketExchangeRates } = useWebSocket()
  
  // Modal states
  const [portfolioModalOpen, setPortfolioModalOpen] = useState(false)
  const [editingPortfolioItem, setEditingPortfolioItem] = useState<PortfolioItem | null>(null)
  const [alertModalOpen, setAlertModalOpen] = useState(false)
  const [editingAlert, setEditingAlert] = useState<PriceAlert | null>(null)
  const [groupAlertModalOpen, setGroupAlertModalOpen] = useState(false)
  const [groupAbovePct, setGroupAbovePct] = useState<string>('')
  const [groupBelowPct, setGroupBelowPct] = useState<string>('')
  const [groupAboveMsg, setGroupAboveMsg] = useState<string>('')
  const [groupBelowMsg, setGroupBelowMsg] = useState<string>('')
  const [groupReference, setGroupReference] = useState<'investment' | 'current'>('investment')
  const [presetAlertData, setPresetAlertData] = useState<{ 
    symbol: string; 
    currentPrice: number;
    portfolioItem?: {
      amount: number;
      price_buy: number;
      commission?: number;
      total_investment_text?: string;
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
  
  // Alert current prices state
  const [alertCurrentPrices, setAlertCurrentPrices] = useState<Record<string, number>>({})
  const [loadingAlertPrices, setLoadingAlertPrices] = useState(false)
  
  // Crypto symbol states
  const [cryptoLastUpdated, setCryptoLastUpdated] = useState<string>('')
  const [cryptoLastUpdatedFormatted, setCryptoLastUpdatedFormatted] = useState<string>('')
  const [symbolTimestamps, setSymbolTimestamps] = useState<Record<string, string>>({})
  
  // Binance import states
  const [importingBinance, setImportingBinance] = useState(false)
  const [importMessage, setImportMessage] = useState<string>('')
  
  // Bitfinex import states
  const [importingBitfinex, setImportingBitfinex] = useState(false)
  const [importBitfinexMessage, setImportBitfinexMessage] = useState<string>('')
  
  // CSV import states
  const [csvImportOpen, setCsvImportOpen] = useState(false)
  const [csvFile, setCsvFile] = useState<File | null>(null)
  const [csvPreview, setCsvPreview] = useState<any>(null)
  const [importingCSV, setImportingCSV] = useState(false)
  const [csvMessage, setCsvMessage] = useState<string>('')

  // Credential check dialog states
  const [credentialDialogOpen, setCredentialDialogOpen] = useState(false)
  const [credentialDialogType, setCredentialDialogType] = useState<'binance' | 'bitfinex' | 'telegram' | null>(null)

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
      setLastUpdated(rates.last_updated_timestamp || rates.last_updated)
      setLastUpdatedFormatted(rates.last_updated_formatted || rates.last_updated)
    } catch (error) {
      console.error('Failed to load exchange rates:', error)
    }
  }

  // Function to convert USD price to selected currency
  const convertToCurrency = (usdPrice: number, targetCurrency: string): number => {
    if (targetCurrency === 'USD') return usdPrice
    if (!exchangeRates[targetCurrency]) return usdPrice
    return usdPrice * exchangeRates[targetCurrency]
  }

  // Function to fetch current prices for alert symbols
  const loadAlertCurrentPrices = async () => {
    if (alerts.length === 0) return
    
    setLoadingAlertPrices(true)
    try {
      const uniqueSymbols = Array.from(new Set(alerts.map(alert => alert.symbol)))
      const prices: Record<string, number> = {}
      
      for (const symbol of uniqueSymbols) {
        try {
          const data = await apiClient.getSymbolPrice(symbol)
          const usdPrice = data.price
          const convertedPrice = convertToCurrency(usdPrice, selectedCurrency)
          prices[symbol] = convertedPrice
        } catch (error) {
          console.error(`Failed to fetch price for ${symbol}:`, error)
          prices[symbol] = 0
        }
      }
      
      setAlertCurrentPrices(prices)
    } catch (error) {
      console.error('Failed to load alert current prices:', error)
    } finally {
      setLoadingAlertPrices(false)
    }
  }


  // Function to calculate percentage difference between current price and threshold
  const calculatePriceDifference = (currentPrice: number, thresholdPrice: number) => {
    if (currentPrice === 0) return { percentage: 0, isAbove: false }
    const percentage = ((currentPrice - thresholdPrice) / thresholdPrice) * 100
    return {
      percentage: Math.abs(percentage),
      isAbove: currentPrice > thresholdPrice
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
      // Use shared refresh utility
      const { currencyResult, cryptoResult } = await refreshAllData()
      
      setLastUpdated(currencyResult.last_updated)
      
      // Reload exchange rates
      await loadExchangeRates()
      // Reload crypto timestamps
      await loadCryptoTimestamps()
      // Reload portfolio data with new rates and prices
      fetchPortfolio()
      fetchSummary()
    } catch (error) {
      console.error('Failed to refresh data:', error)
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

  // Load portfolio preferences from user when available
  useEffect(() => {
    if (user && isHydrated) {
      loadPreferencesFromUser(user)
      if (user.preferred_currency) {
        const { setCurrencyFromUserPreference } = usePortfolioStore.getState()
        setCurrencyFromUserPreference(user.preferred_currency as any)
      }
    }
  }, [user, isHydrated, loadPreferencesFromUser])

  // Debounced symbol filter state
  const [debouncedSymbolFilter, setDebouncedSymbolFilter] = useState(filters.symbol)

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSymbolFilter(filters.symbol)
    }, 300)
    return () => clearTimeout(timer)
  }, [filters.symbol])

  // Load alert current prices when alerts or exchange rates change
  useEffect(() => {
    if (alerts.length > 0 && Object.keys(exchangeRates).length > 0) {
      loadAlertCurrentPrices()
    }
  }, [alerts, exchangeRates, selectedCurrency])

  // Periodic refresh of timestamps and alerts
  useEffect(() => {
    const refreshInterval = process.env.NEXT_PUBLIC_FRONTEND_REFRESH_INTERVAL 
      ? parseInt(process.env.NEXT_PUBLIC_FRONTEND_REFRESH_INTERVAL) 
      : 30000 // Default 30 seconds
    
    const interval = setInterval(() => {
      loadCryptoTimestamps()
      // Also refresh alerts to remove triggered ones
      fetchAlerts()
    }, refreshInterval)

    return () => clearInterval(interval)
  }, [fetchAlerts])

  // Use unified currency formatting functions
  const formatCurrencyAmount = (amount: number) => formatCurrency(amount, selectedCurrency as Currency)
  const formatCurrencyWholeAmount = (amount: number) => formatCurrencyWhole(amount, selectedCurrency as Currency)
  const formatPercentAmount = (percent: number) => formatPercent(percent)
  const formatCryptoAmountValue = (amount: number, symbol: string) => formatCryptoAmount(amount, symbol)
  const formatInvestmentAmount = (amount: number) => formatInvestmentText(amount, selectedCurrency as Currency)


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
    if (window.confirm('Are you sure you want to delete this portfolio item?')) {
      await deleteItem(id)
    }
  }

  const handleImportFromBinance = async () => {
    if (!window.confirm('This will import your entire Binance portfolio. Continue?')) {
      return
    }

    setImportingBinance(true)
    setImportMessage('')

    try {
      const result = await apiClient.importBinancePortfolio()

      if (result.success) {
        setImportMessage(`Successfully imported ${result.items_imported} items!`)
        // Refresh portfolio data
        await fetchPortfolio()
        await fetchSummary()
        // Clear message after 5 seconds
        setTimeout(() => setImportMessage(''), 5000)
      } else {
        // Check for missing credentials error in message
        if (result.message?.includes('No Binance credentials') || result.message?.includes('credentials')) {
          setCredentialDialogType('binance')
          setCredentialDialogOpen(true)
        } else {
          setImportMessage(result.message || 'Import failed')
        }
      }
    } catch (error: any) {
      console.error('Binance import error:', error)
      // Check for missing credentials error in the error response
      const errorMessage = error.response?.data?.detail || error.message || ''
      if (errorMessage.includes('No Binance credentials') || errorMessage.includes('credentials')) {
        setCredentialDialogType('binance')
        setCredentialDialogOpen(true)
      } else {
        setImportMessage(errorMessage || 'Failed to import from Binance')
      }
    } finally {
      setImportingBinance(false)
    }
  }

  const handleImportFromBitfinex = async () => {
    if (!window.confirm('This will import your entire Bitfinex portfolio. Continue?')) {
      return
    }

    setImportingBitfinex(true)
    setImportBitfinexMessage('')

    try {
      const result = await apiClient.importBitfinexPortfolio()

      if (result.success) {
        setImportBitfinexMessage(`Successfully imported ${result.items_imported} items!`)
        // Refresh portfolio data
        await fetchPortfolio()
        await fetchSummary()
        // Clear message after 5 seconds
        setTimeout(() => setImportBitfinexMessage(''), 5000)
      } else {
        // Check for missing credentials error in message
        if (result.message?.includes('No Bitfinex credentials') || result.message?.includes('credentials')) {
          setCredentialDialogType('bitfinex')
          setCredentialDialogOpen(true)
        } else {
          setImportBitfinexMessage(result.message || 'Import failed')
        }
      }
    } catch (error: any) {
      console.error('Bitfinex import error:', error)
      // Check for missing credentials error in the error response
      const errorMessage = error.response?.data?.detail || error.message || ''
      if (errorMessage.includes('No Bitfinex credentials') || errorMessage.includes('credentials')) {
        setCredentialDialogType('bitfinex')
        setCredentialDialogOpen(true)
      } else {
        setImportBitfinexMessage(errorMessage || 'Failed to import from Bitfinex')
      }
    } finally {
      setImportingBitfinex(false)
    }
  }

  const handleCSVFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    if (!file.name.endsWith('.csv')) {
      setCsvMessage('Please select a CSV file')
      return
    }

    setCsvFile(file)
    setCsvMessage('Uploading and parsing CSV...')

    try {
      const result = await apiClient.uploadCSV(file)

      if (result.success) {
        setCsvPreview(result)
        setCsvMessage(`Found ${result.aggregated_items.length} positions from ${result.detected_exchange}`)
      } else {
        setCsvMessage(result.message)
      }
    } catch (error: any) {
      console.error('CSV upload error:', error)
      setCsvMessage(error.response?.data?.detail || 'Failed to parse CSV file')
    }
  }

  const handleCSVImport = async () => {
    if (!csvFile || !csvPreview?.detected_exchange) {
      setCsvMessage('Please upload a CSV file first')
      return
    }

    console.log('🔵 Starting CSV import:', { 
      fileName: csvFile.name, 
      exchange: csvPreview.detected_exchange,
      items: csvPreview.aggregated_items.length 
    })

    setImportingCSV(true)
    setCsvMessage('Importing...')

    try {
      const result = await apiClient.executeCSVImport(csvFile, csvPreview.detected_exchange)
      console.log('✅ CSV import result:', result)

      if (result.success) {
        setCsvMessage(`Successfully imported ${result.items_imported} items!`)
        // Refresh portfolio data
        await fetchPortfolio()
        await fetchSummary()
        // Close modal and reset after 3 seconds
        setTimeout(() => {
          setCsvImportOpen(false)
          setCsvFile(null)
          setCsvPreview(null)
          setCsvMessage('')
        }, 3000)
      } else {
        setCsvMessage(result.message || 'Import failed')
      }
    } catch (error: any) {
      console.error('CSV import error:', error)
      setCsvMessage(error.response?.data?.detail || 'Failed to import CSV')
    } finally {
      setImportingCSV(false)
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
    setPresetAlertData(null) // Clear any preset data for generic alert creation
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
        commission: item.commission || 0,
        total_investment_text: item.total_investment_text,
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
    if (window.confirm('Are you sure you want to delete this alert?')) {
      await deleteAlert(id)
    }
  }

  const handleSaveAlert = async (alert: PriceAlertCreate | PriceAlertUpdate) => {
    // Check for Telegram settings when creating a new alert
    if (!editingAlert && user) {
      // Check if user has Telegram settings configured
      if (!user.telegram_bot_token || !user.telegram_chat_id) {
        // Open credential dialog for Telegram
        setCredentialDialogType('telegram')
        setCredentialDialogOpen(true)
        // Don't save the alert if Telegram is not configured
        return
      }
    }

    // Save the alert if we have Telegram settings or are editing an existing alert
    if (editingAlert) {
      await updateAlert(editingAlert.id, alert as PriceAlertUpdate)
    } else {
      await createAlert(alert as PriceAlertCreate)
    }
  }

  const handleCreateGroupAlerts = async () => {
    if (!user) return
    const above = groupAbovePct !== '' ? parseFloat(groupAbovePct) : user.default_alert_percentage_above
    const below = groupBelowPct !== '' ? parseFloat(groupBelowPct) : user.default_alert_percentage_below
    if (above == null && below == null) {
      alert('Please set at least one percentage (Above or Below) in the form or in your profile settings.')
      return
    }

    // Collect unique symbols from portfolio
    const symbols = Array.from(new Set(items.map(i => i.symbol)))
    for (const symbol of symbols) {
      // Find portfolio item for this symbol
      const item = items.find(i => i.symbol === symbol)
      if (!item) continue

      // Determine base price depending on reference selection
      let basePrice = 0
      if (groupReference === 'investment') {
        // Use investment price (total_investment/amount or calculate from price_buy)
        if (item.amount > 0) {
          let invested = item.total_investment_text ? parseFloat((item.total_investment_text.match(/[\d,\.\s]+/) || ['0'])[0].replace(/[\s,]/g, '')) : (item.amount * item.price_buy + (item.commission || 0))
          basePrice = invested / item.amount
        }
      } else {
        // Use current price from portfolio item or alert prices
        basePrice = item.current_price || alertCurrentPrices[symbol] || 0
      }

      if (!basePrice || basePrice <= 0) continue

      // Create ABOVE alert
      if (above != null) {
        const threshold = basePrice * (1 + above / 100)
        await createAlert({ 
          symbol, 
          alert_type: 'ABOVE', 
          threshold_price: threshold, 
          message: groupAboveMsg || `${symbol} price alert triggered!`,
          base_currency: selectedCurrency 
        })
      }
      // Create BELOW alert
      if (below != null) {
        const threshold = basePrice * (1 - below / 100)
        await createAlert({ 
          symbol, 
          alert_type: 'BELOW', 
          threshold_price: threshold, 
          message: groupBelowMsg || `${symbol} price alert triggered!`,
          base_currency: selectedCurrency 
        })
      }
    }
    await fetchAlerts()
    setGroupAlertModalOpen(false)
    setGroupAbovePct('')
    setGroupBelowPct('')
    setGroupAboveMsg('')
    setGroupBelowMsg('')
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
                <Button variant="outline" title="Profile">
                  <User className="h-4 w-4" />
                </Button>
              </Link>
              <Button variant="outline" onClick={logout} title="Logout">
                <LogOut className="h-4 w-4" />
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
                  <div className={`w-1.5 h-1.5 rounded-full ${getFreshnessColorClass(getDataFreshness(lastUpdated))}`} />
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
                  <div className={`w-1.5 h-1.5 rounded-full ${getFreshnessColorClass(getDataFreshness(cryptoLastUpdated))}`} />
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
                ) : summary ? formatCurrencyWholeAmount(summary.total_value) : 'Loading...'}
              </div>
              <div className="text-lg text-blue-600 font-medium transition-all duration-300 ease-in-out">
                {(loading || currencyChanging) ? (
                  <span className="animate-pulse">Loading...</span>
                ) : summary ? formatCurrencyWholeAmount(summary.total_invested) : 'Loading...'}
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
              ) : summary ? formatCurrencyWholeAmount(summary.total_pnl) : 'Loading...'}
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
              ) : summary ? formatPercentAmount(summary.total_pnl_percent) : 'Loading...'}
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
      {/* Filtering and sorting logic */}
      {(() => {
        // Calculate investment for each item
        const calculateInvestment = (item: PortfolioItem) => (item.amount * item.price_buy) + item.commission

        // Filter items
        let filteredItems = items.filter(item => {
          // Symbol filter (using debounced value)
          if (debouncedSymbolFilter && !item.symbol.toLowerCase().includes(debouncedSymbolFilter.toLowerCase())) {
            return false
          }

          // Platform filter
          if (filters.platform !== 'All' && item.source !== filters.platform) {
            return false
          }

          // Investment range filter
          const investment = calculateInvestment(item)
          if (filters.investmentMin !== undefined && investment < filters.investmentMin) {
            return false
          }
          if (filters.investmentMax !== undefined && investment > filters.investmentMax) {
            return false
          }

          // P&L range filter
          if (filters.pnlMin !== undefined && item.pnl !== undefined && item.pnl < filters.pnlMin) {
            return false
          }
          if (filters.pnlMax !== undefined && item.pnl !== undefined && item.pnl > filters.pnlMax) {
            return false
          }

          // P&L % range filter
          if (filters.pnlPercentMin !== undefined && item.pnl_percent !== undefined && item.pnl_percent < filters.pnlPercentMin) {
            return false
          }
          if (filters.pnlPercentMax !== undefined && item.pnl_percent !== undefined && item.pnl_percent > filters.pnlPercentMax) {
            return false
          }

          return true
        })

        // Sort items
        const sortedItems = [...filteredItems].sort((a, b) => {
          let aVal: any
          let bVal: any

          switch (sort.by) {
            case 'symbol':
              aVal = a.symbol
              bVal = b.symbol
              break
            case 'investment':
              aVal = calculateInvestment(a)
              bVal = calculateInvestment(b)
              break
            case 'platform':
              aVal = a.source || ''
              bVal = b.source || ''
              break
            case 'pnl':
              aVal = a.pnl || 0
              bVal = b.pnl || 0
              break
            case 'pnl_percent':
              aVal = a.pnl_percent || 0
              bVal = b.pnl_percent || 0
              break
            case 'current_value':
              aVal = a.current_value || 0
              bVal = b.current_value || 0
              break
            default:
              return 0
          }

          if (aVal < bVal) return sort.dir === 'asc' ? -1 : 1
          if (aVal > bVal) return sort.dir === 'asc' ? 1 : -1
          return 0
        })

        // Get unique platforms for filter dropdown
        const platforms = ['All', ...Array.from(new Set(items.map(item => item.source).filter(Boolean)))]

        return (
          <Card>
            <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Portfolio</CardTitle>
              <CardDescription>Your cryptocurrency holdings</CardDescription>
              {importMessage && (
                <div className={`mt-2 text-sm ${importMessage.includes('Successfully') ? 'text-green-600' : 'text-red-600'}`}>
                  {importMessage}
                </div>
              )}
              {importBitfinexMessage && (
                <div className={`mt-2 text-sm ${importBitfinexMessage.includes('Successfully') ? 'text-green-600' : 'text-red-600'}`}>
                  {importBitfinexMessage}
                </div>
              )}
            </div>
            <div className="flex gap-2">
              <Button 
                onClick={handleImportFromBinance}
                disabled={importingBinance || importingBitfinex}
                variant="outline"
              >
                {importingBinance ? 'Importing...' : '📥 Import from Binance'}
              </Button>
              <Button 
                onClick={handleImportFromBitfinex}
                disabled={importingBinance || importingBitfinex}
                variant="outline"
              >
                {importingBitfinex ? 'Importing...' : '📥 Import from Bitfinex'}
              </Button>
              <Button 
                onClick={() => setCsvImportOpen(true)}
                disabled={importingBinance || importingBitfinex}
                variant="outline"
              >
                📄 Import from CSV
              </Button>
              <Button onClick={handleAddPortfolioItem}>
                Add New Item
              </Button>
            </div>
          </div>
        </CardHeader>
        {/* Filter and Sort Controls */}
        <div className="px-6 py-4 border-b">
          <div className="flex flex-col gap-4">
            {/* Row 1: View toggle and Sort */}
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">View:</span>
                <div className="flex border rounded-md">
                  <Button
                    variant={viewMode === 'cards' ? 'default' : 'ghost'}
                    size="sm"
                    onClick={() => setViewMode('cards')}
                    className="rounded-r-none"
                  >
                    Cards
                  </Button>
                  <Button
                    variant={viewMode === 'table' ? 'default' : 'ghost'}
                    size="sm"
                    onClick={() => setViewMode('table')}
                    className="rounded-l-none"
                  >
                    Table
                  </Button>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Sort:</span>
                <select
                  value={sort.by}
                  onChange={(e) => setSort(e.target.value as any)}
                  className="px-3 py-1 border rounded text-sm"
                >
                  <option value="symbol">Symbol</option>
                  <option value="investment">Investment</option>
                  <option value="current_value">Current Value</option>
                  <option value="platform">Platform</option>
                  <option value="pnl">P&L</option>
                  <option value="pnl_percent">P&L %</option>
                </select>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setSort(sort.by, sort.dir === 'asc' ? 'desc' : 'asc')}
                >
                  {sort.dir === 'asc' ? '↑' : '↓'}
                </Button>
              </div>
            </div>
            {/* Row 2: Filters */}
            <div className="flex items-center gap-4 flex-wrap">
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Symbol:</span>
                <Input
                  type="text"
                  placeholder="Filter by symbol"
                  value={filters.symbol}
                  onChange={(e) => setFilters({ symbol: e.target.value })}
                  className="w-32"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Platform:</span>
                <select
                  value={filters.platform}
                  onChange={(e) => setFilters({ platform: e.target.value })}
                  className="px-3 py-1 border rounded text-sm"
                >
                  {platforms.map(p => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Investment:</span>
                <Input
                  type="number"
                  placeholder="Min"
                  value={filters.investmentMin || ''}
                  onChange={(e) => setFilters({ investmentMin: e.target.value ? parseFloat(e.target.value) : undefined })}
                  className="w-24"
                />
                <span>-</span>
                <Input
                  type="number"
                  placeholder="Max"
                  value={filters.investmentMax || ''}
                  onChange={(e) => setFilters({ investmentMax: e.target.value ? parseFloat(e.target.value) : undefined })}
                  className="w-24"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">P&L:</span>
                <Input
                  type="number"
                  placeholder="Min"
                  value={filters.pnlMin || ''}
                  onChange={(e) => setFilters({ pnlMin: e.target.value ? parseFloat(e.target.value) : undefined })}
                  className="w-24"
                />
                <span>-</span>
                <Input
                  type="number"
                  placeholder="Max"
                  value={filters.pnlMax || ''}
                  onChange={(e) => setFilters({ pnlMax: e.target.value ? parseFloat(e.target.value) : undefined })}
                  className="w-24"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">P&L %:</span>
                <Input
                  type="number"
                  placeholder="Min"
                  value={filters.pnlPercentMin || ''}
                  onChange={(e) => setFilters({ pnlPercentMin: e.target.value ? parseFloat(e.target.value) : undefined })}
                  className="w-24"
                />
                <span>-</span>
                <Input
                  type="number"
                  placeholder="Max"
                  value={filters.pnlPercentMax || ''}
                  onChange={(e) => setFilters({ pnlPercentMax: e.target.value ? parseFloat(e.target.value) : undefined })}
                  className="w-24"
                />
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setFilters({ symbol: '', platform: 'All' })}
              >
                Clear Filters
              </Button>
              <div className="ml-auto text-sm text-muted-foreground">
                Showing {sortedItems.length} of {items.length} items
              </div>
            </div>
          </div>
        </div>
        <CardContent>
          {loading ? (
            <div className="text-center py-8">Loading portfolio...</div>
          ) : sortedItems.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No portfolio items found. Add some cryptocurrencies to get started.
            </div>
          ) : viewMode === 'cards' ? (
            <div className="space-y-4">
              {sortedItems.map((item) => {
                const investment = (item.amount * item.price_buy) + item.commission
                return (
                <div key={item.id} className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="flex items-center space-x-4">
                    <div className="font-semibold">{item.symbol}</div>
                    <div className="text-sm font-medium text-blue-600 bg-blue-50 px-2 py-1 rounded">
                      {formatInvestmentAmount(investment)}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {formatCryptoAmountValue(item.amount, item.symbol)} @ {formatCurrencyAmount(item.price_buy)}
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
                        ) : item.current_price ? formatCurrencyAmount(item.current_price) : 'N/A'}
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
                          ) : formatCurrencyAmount(item.current_value)}
                        </div>
                        {item.pnl !== undefined && (
                          <div className={`text-sm transition-all duration-300 ease-in-out ${item.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {(loading || currencyChanging) ? (
                              <span className="animate-pulse">Loading...</span>
                            ) : (
                              <>
                                {formatCurrencyAmount(item.pnl)} ({formatPercentAmount(item.pnl_percent || 0)})
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
              )})}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground cursor-pointer hover:bg-gray-50" onClick={() => setSort('symbol')}>
                      Symbol {sort.by === 'symbol' && (sort.dir === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground cursor-pointer hover:bg-gray-50" onClick={() => setSort('investment')}>
                      Investment {sort.by === 'investment' && (sort.dir === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground cursor-pointer hover:bg-gray-50" onClick={() => setSort('platform')}>
                      Platform {sort.by === 'platform' && (sort.dir === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground cursor-pointer hover:bg-gray-50" onClick={() => setSort('pnl')}>
                      P&L {sort.by === 'pnl' && (sort.dir === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground cursor-pointer hover:bg-gray-50" onClick={() => setSort('pnl_percent')}>
                      P&L % {sort.by === 'pnl_percent' && (sort.dir === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedItems.map((item) => {
                    const investment = calculateInvestment(item)
                    return (
                      <tr key={item.id} className="border-b hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium">{item.symbol}</td>
                        <td className="px-4 py-3">
                          <div className="text-sm">
                            <div className="font-medium">{formatCurrencyAmount(investment)}</div>
                            <div className="text-xs text-muted-foreground">
                              {formatCryptoAmountValue(item.amount, item.symbol)} @ {formatCurrencyAmount(item.price_buy)}
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sm text-muted-foreground">{item.source || 'N/A'}</td>
                        <td className="px-4 py-3 text-right">
                          {item.pnl !== undefined ? (
                            <div className={`text-sm font-medium ${item.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                              {formatCurrencyAmount(item.pnl)}
                            </div>
                          ) : (
                            <span className="text-sm text-muted-foreground">N/A</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {item.pnl_percent !== undefined ? (
                            <div className={`text-sm font-medium ${item.pnl_percent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                              {formatPercentAmount(item.pnl_percent)}
                            </div>
                          ) : (
                            <span className="text-sm text-muted-foreground">N/A</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleAddAlertForCoin(item)}
                              className="text-blue-600 hover:text-blue-700"
                              disabled={!item.current_price}
                              title="Set Alert"
                            >
                              ⚠️
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleEditPortfolioItem(item)}
                              title="Edit"
                            >
                              ✏️
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleDeletePortfolioItem(item.id)}
                              className="text-red-600 hover:text-red-700"
                              title="Delete"
                            >
                              🗑️
                            </Button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
        )
      })()}

      {/* Alerts */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Price Alerts</CardTitle>
              <CardDescription>Active price notifications</CardDescription>
            </div>
            <div className="flex items-center space-x-2">
              <Button 
                onClick={() => fetchAlerts()}
                variant="outline"
                size="sm"
                disabled={loading}
              >
                {loading ? 'Refreshing...' : '🔄'}
              </Button>
              <Button onClick={handleAddAlert}>
                Create Alert
              </Button>
              <Button onClick={() => {
                setGroupAbovePct(user?.default_alert_percentage_above?.toString() || '')
                setGroupBelowPct(user?.default_alert_percentage_below?.toString() || '')
                setGroupAlertModalOpen(true)
              }} variant="secondary">
                Create Group Alert
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {alerts.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No active alerts. Create some price alerts to get notified.
            </div>
          ) : (
            <div className="space-y-2">
              {alerts.map((alert) => {
                const currentPrice = alertCurrentPrices[alert.symbol] || 0
                const priceDiff = calculatePriceDifference(currentPrice, alert.threshold_price)
                
                return (
                  <div key={alert.id} className="flex items-center justify-between p-3 border rounded">
                    {/* Left side - Current price and percentage difference */}
                    <div className="flex items-center space-x-4">
                      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 min-w-[120px]">
                        <div className="text-xs text-blue-600 font-medium mb-1">
                          {alert.symbol} Current Price
                        </div>
                        <div className="text-lg font-bold text-blue-800">
                          {loadingAlertPrices ? (
                            <div className="animate-pulse">Loading...</div>
                          ) : currentPrice > 0 ? (
                            formatCurrencyAmount(currentPrice)
                          ) : (
                            'N/A'
                          )}
                        </div>
                        {currentPrice > 0 && (
                          <div className={`text-xs mt-1 ${
                            priceDiff.isAbove ? 'text-green-600' : 'text-red-600'
                          }`}>
                            {priceDiff.isAbove ? '📈' : '📉'} {priceDiff.percentage.toFixed(1)}% {priceDiff.isAbove ? 'above' : 'below'} threshold
                          </div>
                        )}
                      </div>
                      
                      {/* Alert details */}
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="font-medium">{alert.symbol}</span>
                          <span className="text-sm text-muted-foreground">
                            {alert.alert_type} {formatCurrencyAmount(alert.threshold_price)}
                          </span>
                        </div>
                        {alert.message && (
                          <div className="text-sm text-muted-foreground mt-1">
                            {alert.message}
                          </div>
                        )}
                      </div>
                    </div>
                    
                    {/* Right side - Status and actions */}
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
                )
              })}
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
        availableSymbols={trackedSymbols.map(s => s.symbol)}
        defaultAlertPercentageAbove={user?.default_alert_percentage_above}
        defaultAlertPercentageBelow={user?.default_alert_percentage_below}
      />

      {/* Group Alert Modal */}
      {groupAlertModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md m-4">
            <CardHeader>
              <CardTitle>Create Group Alerts</CardTitle>
              <CardDescription>Apply alerts to every symbol in your portfolio</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Reference</label>
                  <div className="grid grid-cols-2 gap-2">
                  <label className={`flex items-center justify-center space-x-2 p-2 border rounded-lg cursor-pointer ${groupReference === 'investment' ? 'bg-blue-100 border-blue-300' : 'bg-gray-50 border-gray-300'}`}>
                      <input type="radio" checked={groupReference === 'investment'} onChange={() => setGroupReference('investment')} />
                      <span className="text-sm">Investment cost/avg (blue value)</span>
                    </label>
                    <label className={`flex items-center justify-center space-x-2 p-2 border rounded-lg cursor-pointer ${groupReference === 'current' ? 'bg-green-100 border-green-300' : 'bg-gray-50 border-gray-300'}`}>
                      <input type="radio" checked={groupReference === 'current'} onChange={() => setGroupReference('current')} />
                      <span className="text-sm">Current price (green value)</span>
                    </label>
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">
                    {groupReference === 'investment' ? 'Above Investment (%)' : 'Above Current Price (%)'}
                  </label>
                  <Input
                    type="number"
                    min="0"
                    max="1000"
                    step="0.1"
                    value={groupAbovePct}
                    onChange={(e) => setGroupAbovePct(e.target.value)}
                  />
                  <p className="text-xs text-gray-500">Leave empty to use your profile default or skip ABOVE alerts.</p>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">ABOVE Alert Message</label>
                  <Input
                    type="text"
                    value={groupAboveMsg}
                    onChange={(e) => setGroupAboveMsg(e.target.value)}
                    placeholder="e.g., Price has increased significantly!"
                  />
                  <p className="text-xs text-gray-500">This message will be sent to Telegram when the ABOVE alert triggers.</p>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">
                    {groupReference === 'investment' ? 'Below Investment (%)' : 'Below Current Price (%)'}
                  </label>
                  <Input
                    type="number"
                    min="0"
                    max="1000"
                    step="0.1"
                    value={groupBelowPct}
                    onChange={(e) => setGroupBelowPct(e.target.value)}
                  />
                  <p className="text-xs text-gray-500">Leave empty to use your profile default or skip BELOW alerts.</p>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">BELOW Alert Message</label>
                  <Input
                    type="text"
                    value={groupBelowMsg}
                    onChange={(e) => setGroupBelowMsg(e.target.value)}
                    placeholder="e.g., Price has dropped significantly!"
                  />
                  <p className="text-xs text-gray-500">This message will be sent to Telegram when the BELOW alert triggers.</p>
                </div>
                <div className="flex items-center justify-end space-x-2 pt-2">
                  <Button variant="outline" onClick={() => setGroupAlertModalOpen(false)}>Cancel</Button>
                  <Button onClick={handleCreateGroupAlerts}>Create for All</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* CSV Import Modal */}
      {csvImportOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-3xl max-h-[90vh] overflow-y-auto m-4">
            <CardHeader>
              <CardTitle>Import from CSV</CardTitle>
              <CardDescription>Upload your cryptocurrency transaction CSV file</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* File Upload */}
              <div>
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleCSVFileSelect}
                  className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                />
              </div>

              {/* Message */}
              {csvMessage && (
                <div className={`p-3 rounded ${
                  csvMessage.includes('Successfully') ? 'bg-green-50 text-green-700' : 'bg-yellow-50 text-yellow-700'
                }`}>
                  {csvMessage}
                </div>
              )}

              {/* Preview */}
              {csvPreview?.success && (
                <div>
                  <h3 className="font-semibold mb-2">Preview: {csvPreview.aggregated_items.length} positions</h3>
                  <div className="border rounded-lg overflow-hidden max-h-96 overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 sticky top-0">
                        <tr>
                          <th className="px-3 py-2 text-left">Symbol</th>
                          <th className="px-3 py-2 text-right">Quantity</th>
                          <th className="px-3 py-2 text-right">Price</th>
                          <th className="px-3 py-2 text-right">Value</th>
                          <th className="px-3 py-2 text-right">Fees</th>
                          <th className="px-3 py-2 text-left">Date</th>
                          <th className="px-3 py-2 text-left">Currency</th>
                        </tr>
                      </thead>
                      <tbody>
                        {csvPreview.aggregated_items.map((item: any, idx: number) => (
                          <tr key={idx} className="border-t hover:bg-gray-50">
                            <td className="px-3 py-2 font-medium">{item.symbol}</td>
                            <td className="px-3 py-2 text-right">{item.quantity.toFixed(8)}</td>
                            <td className="px-3 py-2 text-right">{item.price.toFixed(2)}</td>
                            <td className="px-3 py-2 text-right">{item.value ? item.value.toFixed(2) : (item.quantity * item.price).toFixed(2)}</td>
                            <td className="px-3 py-2 text-right">{item.fees ? item.fees.toFixed(2) : '0.00'}</td>
                            <td className="px-3 py-2">{item.date || 'N/A'}</td>
                            <td className="px-3 py-2">{item.currency}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2 pt-4">
                <Button
                  onClick={handleCSVImport}
                  disabled={!csvPreview?.success || importingCSV}
                  className="flex-1"
                >
                  {importingCSV ? 'Importing...' : 'Import Portfolio'}
                </Button>
                <Button
                  onClick={() => {
                    setCsvImportOpen(false)
                    setCsvFile(null)
                    setCsvPreview(null)
                    setCsvMessage('')
                  }}
                  variant="outline"
                >
                  Close
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Credential Check Dialog */}
      <Dialog open={credentialDialogOpen} onOpenChange={setCredentialDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>
              {credentialDialogType === 'binance' && 'Binance Credentials Required'}
              {credentialDialogType === 'bitfinex' && 'Bitfinex Credentials Required'}
              {credentialDialogType === 'telegram' && 'Telegram Settings Required'}
            </DialogTitle>
          </DialogHeader>
          <div className="py-2">
            <p className="text-sm text-gray-600">
              {credentialDialogType === 'binance' && 'Please configure your Binance API credentials to import your portfolio from Binance.'}
              {credentialDialogType === 'bitfinex' && 'Please configure your Bitfinex API credentials to import your portfolio from Bitfinex.'}
              {credentialDialogType === 'telegram' && 'Please configure your Telegram settings to receive price alerts.'}
            </p>
          </div>
          <div className="py-4">
            <div className="space-y-4">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="text-sm text-blue-700">
                  <p className="font-medium mb-2">
                    {credentialDialogType === 'binance' && '🔐 Binance API Setup Required'}
                    {credentialDialogType === 'bitfinex' && '🔐 Bitfinex API Setup Required'}
                    {credentialDialogType === 'telegram' && '📱 Telegram Setup Required'}
                  </p>
                  <p>
                    {credentialDialogType === 'binance' && 'You need to add your Binance API Key and Secret in your profile settings.'}
                    {credentialDialogType === 'bitfinex' && 'You need to add your Bitfinex API Key and Secret in your profile settings.'}
                    {credentialDialogType === 'telegram' && 'You need to add your Telegram Bot Token and Chat ID in your profile settings.'}
                  </p>
                </div>
              </div>
            </div>
          </div>
          
          <DialogFooter>
            <Button 
              type="button" 
              variant="outline" 
              onClick={() => setCredentialDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button 
              type="button"
              onClick={() => {
                setCredentialDialogOpen(false)
                router.push(`/profile?tab=${credentialDialogType}`)
              }}
            >
              Go to Settings
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}


