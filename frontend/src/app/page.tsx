'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { usePortfolioStore } from '@/stores/portfolioStore'
import { useAlertsStore } from '@/stores/alertsStore'
import { useSymbolsStore } from '@/stores/symbolsStore'
import { useWebSocket } from '@/hooks/useWebSocket'
import { PortfolioModal } from '@/components/PortfolioModal'
import { AlertModal } from '@/components/AlertModal'
import { PortfolioItem, PortfolioCreate, PortfolioUpdate, PriceAlert, PriceAlertCreate, PriceAlertUpdate } from '@/types'
import { apiClient } from '@/lib/api'

export default function Home() {
  const { items, summary, selectedCurrency, loading, fetchPortfolio, fetchSummary, setCurrency, createItem, updateItem, deleteItem } = usePortfolioStore()
  const { alerts, fetchAlerts, createAlert, updateAlert, deleteAlert } = useAlertsStore()
  const { trackedSymbols, fetchTrackedSymbols } = useSymbolsStore()
  const { isConnected, subscribeToPrices, subscribeToAlerts } = useWebSocket()

  // Modal states
  const [portfolioModalOpen, setPortfolioModalOpen] = useState(false)
  const [editingPortfolioItem, setEditingPortfolioItem] = useState<PortfolioItem | null>(null)
  const [alertModalOpen, setAlertModalOpen] = useState(false)
  const [editingAlert, setEditingAlert] = useState<PriceAlert | null>(null)
  
  // Currency states
  const [exchangeRates, setExchangeRates] = useState<Record<string, number>>({})
  const [lastUpdated, setLastUpdated] = useState<string>('')
  const [refreshingRates, setRefreshingRates] = useState(false)

  useEffect(() => {
    // Fetch initial data
    fetchPortfolio()
    fetchSummary()
    fetchAlerts()
    fetchTrackedSymbols()
    loadExchangeRates()
  }, [fetchPortfolio, fetchSummary, fetchAlerts, fetchTrackedSymbols])

  const loadExchangeRates = async () => {
    try {
      const rates = await apiClient.getExchangeRates()
      setExchangeRates(rates.rates)
      setLastUpdated(rates.last_updated)
    } catch (error) {
      console.error('Failed to load exchange rates:', error)
    }
  }

  const refreshExchangeRates = async () => {
    setRefreshingRates(true)
    try {
      const result = await apiClient.refreshExchangeRates()
      setLastUpdated(result.last_updated)
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

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold">Crypto AI Agent v2.0</h1>
          <p className="text-muted-foreground">Next.js + FastAPI + Telegram + AI</p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <span className="text-sm text-muted-foreground">Currency:</span>
            <select 
              value={selectedCurrency} 
              onChange={(e) => setCurrency(e.target.value as any)}
              className="px-3 py-1 border rounded"
            >
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
              <option value="CZK">CZK</option>
            </select>
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
          {lastUpdated && (
            <div className="text-xs text-muted-foreground">
              Rates: {lastUpdated}
            </div>
          )}
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
              <div className="text-2xl font-bold">
                {summary ? formatCurrencyWhole(summary.total_value) : 'Loading...'}
              </div>
              <div className="text-lg text-blue-600 font-medium">
                Invested: {summary ? formatCurrencyWhole(summary.total_invested) : 'Loading...'}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total P&L</CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${summary && summary.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {summary ? formatCurrencyWhole(summary.total_pnl) : 'Loading...'}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">P&L %</CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${summary && summary.total_pnl_percent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {summary ? formatPercent(summary.total_pnl_percent) : 'Loading...'}
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
                      <div className="text-sm text-muted-foreground">
                        {item.current_price ? formatCurrency(item.current_price) : 'N/A'}
                      </div>
                    </div>
                    {item.current_value && (
                      <div className="text-right">
                        <div className={`text-sm font-medium px-2 py-1 rounded ${
                          item.current_value >= (item.amount * item.price_buy) + item.commission
                            ? 'text-green-600 bg-green-50'
                            : 'text-red-600 bg-red-50'
                        }`}>
                          {formatCurrency(item.current_value)}
                        </div>
                        {item.pnl !== undefined && (
                          <div className={`text-sm ${item.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {formatCurrency(item.pnl)} ({formatPercent(item.pnl_percent || 0)})
                          </div>
                        )}
                      </div>
                    )}
                    <div className="flex items-center space-x-2">
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
        onClose={() => setAlertModalOpen(false)}
        onSave={handleSaveAlert}
        alert={editingAlert}
      />
    </div>
  )
}


