'use client'

import { useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { usePortfolioStore } from '@/stores/portfolioStore'
import { useAlertsStore } from '@/stores/alertsStore'
import { useSymbolsStore } from '@/stores/symbolsStore'
import { useWebSocket } from '@/hooks/useWebSocket'

export default function Home() {
  const { items, summary, selectedCurrency, loading, fetchPortfolio, fetchSummary, setCurrency } = usePortfolioStore()
  const { alerts, fetchAlerts } = useAlertsStore()
  const { trackedSymbols, fetchTrackedSymbols } = useSymbolsStore()
  const { isConnected, subscribeToPrices, subscribeToAlerts } = useWebSocket()

  useEffect(() => {
    // Fetch initial data
    fetchPortfolio()
    fetchSummary()
    fetchAlerts()
    fetchTrackedSymbols()
  }, [fetchPortfolio, fetchSummary, fetchAlerts, fetchTrackedSymbols])

  useEffect(() => {
    // Subscribe to WebSocket updates
    if (isConnected) {
      subscribeToAlerts()
      if (trackedSymbols.length > 0) {
        const symbols = trackedSymbols.map(s => s.symbol)
        subscribeToPrices(symbols)
      }
    }
  }, [isConnected, trackedSymbols, subscribeToPrices, subscribeToAlerts])

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: selectedCurrency,
    }).format(amount)
  }

  const formatPercent = (percent: number) => {
    return `${percent >= 0 ? '+' : ''}${percent.toFixed(2)}%`
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold">Crypto AI Agent v2.0</h1>
          <p className="text-muted-foreground">Next.js + FastAPI + PostgreSQL + Redis architecture + Telegram + AI</p>
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
          </div>
          <div className="flex items-center space-x-2">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-sm text-muted-foreground">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
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
            <div className="text-2xl font-bold">
              {summary ? formatCurrency(summary.total_value) : 'Loading...'}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total P&L</CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${summary && summary.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {summary ? formatCurrency(summary.total_pnl) : 'Loading...'}
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
          <CardTitle>Portfolio</CardTitle>
          <CardDescription>Your cryptocurrency holdings</CardDescription>
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
                    <div className="text-sm text-muted-foreground">
                      {item.amount} @ {formatCurrency(item.price_buy)}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {item.base_currency}
                    </div>
                  </div>
                  <div className="flex items-center space-x-4">
                    <div className="text-right">
                      <div className="font-semibold">
                        {item.current_price ? formatCurrency(item.current_price) : 'N/A'}
                      </div>
                      {item.pnl !== undefined && (
                        <div className={`text-sm ${item.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {formatCurrency(item.pnl)} ({formatPercent(item.pnl_percent || 0)})
                        </div>
                      )}
                    </div>
                    <Button variant="outline" size="sm">
                      Edit
                    </Button>
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
          <CardTitle>Price Alerts</CardTitle>
          <CardDescription>Active price notifications</CardDescription>
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
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className={`px-2 py-1 text-xs rounded ${
                      alert.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                    }`}>
                      {alert.is_active ? 'Active' : 'Inactive'}
                    </span>
                    <Button variant="outline" size="sm">
                      Edit
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
