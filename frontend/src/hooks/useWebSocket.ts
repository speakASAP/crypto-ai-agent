import { useEffect, useRef, useCallback, useState } from 'react'
import { usePortfolioStore } from '@/stores/portfolioStore'
import { useAlertsStore } from '@/stores/alertsStore'
import { useSymbolsStore } from '@/stores/symbolsStore'
import { PriceUpdateMessage, AlertTriggeredMessage } from '@/types'

interface WebSocketHook {
  isConnected: boolean
  connect: () => void
  disconnect: () => void
  subscribeToPrices: (symbols: string[]) => void
  subscribeToAlerts: () => void
  setExchangeRates: (rates: Record<string, number>) => void
}

export const useWebSocket = (): WebSocketHook => {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const exchangeRatesRef = useRef<Record<string, number>>({})
  
  const { fetchPortfolio, fetchSummary } = usePortfolioStore()
  const { fetchAlerts, fetchHistory } = useAlertsStore()
  const { fetchSymbolPrices } = useSymbolsStore()

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      console.log('WebSocket already connected or connecting, skipping...')
      return
    }

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/'
    console.log('🔌 Connecting to WebSocket:', wsUrl)

    try {
      wsRef.current = new WebSocket(wsUrl)

      wsRef.current.onopen = () => {
        console.log('✅ WebSocket connected')
        setIsConnected(true)
        // Clear any pending reconnection
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current)
          reconnectTimeoutRef.current = null
        }
      }

      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          handleWebSocketMessage(message)
        } catch (error) {
          console.error('❌ Failed to parse WebSocket message:', error)
          console.error('❌ Raw message data:', event.data)
        }
      }

      wsRef.current.onclose = (event) => {
        console.log('🔌 WebSocket disconnected:', event.code, event.reason)
        setIsConnected(false)
        
        // Attempt to reconnect after 5 seconds
        if (event.code !== 1000) { // Not a normal closure
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log('🔄 Attempting to reconnect...')
            connect()
          }, 5000)
        }
      }

      wsRef.current.onerror = (error) => {
        console.error('❌ WebSocket error:', error)
        console.error('WebSocket readyState:', wsRef.current?.readyState)
        console.error('WebSocket URL:', wsUrl)
        console.error('WebSocket error details:', {
          type: error.type,
          target: error.target,
          currentTarget: error.currentTarget
        })
        setIsConnected(false)
      }
    } catch (error) {
      console.error('❌ Failed to create WebSocket connection:', error)
    }
  }, [])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    
    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnected')
      wsRef.current = null
    }
    setIsConnected(false)
  }, [])

  const subscribeToPrices = useCallback((symbols: string[]) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const message = {
        type: 'subscribe',
        symbols: symbols
      }
      wsRef.current.send(JSON.stringify(message))
      console.log('📊 Subscribed to price updates for:', symbols)
    }
  }, [])

  const subscribeToAlerts = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const message = {
        type: 'subscribe_alerts'
      }
      wsRef.current.send(JSON.stringify(message))
      console.log('🔔 Subscribed to alert notifications')
    }
  }, [])

  const handleWebSocketMessage = useCallback((message: any) => {
    switch (message.type) {
      case 'price_update':
        handlePriceUpdate(message as PriceUpdateMessage, exchangeRatesRef.current)
        break
      case 'alert_triggered':
        handleAlertTriggered(message as AlertTriggeredMessage)
        break
      case 'connection_status':
        console.log('📡 Connection status:', message.data)
        break
      default:
        console.log('📨 Unknown message type:', message.type)
    }
  }, [])

  const handlePriceUpdate = useCallback((message: PriceUpdateMessage, exchangeRates?: Record<string, number>) => {
    try {
      console.log('📈 Price update:', message.data)
      
      // Update symbol prices in store
      const { symbol, price, timestamp } = message.data
      const symbolsStore = useSymbolsStore.getState()
      symbolsStore.symbolPrices[symbol] = {
        symbol,
        price,
        timestamp
      }
      
      // Update portfolio values locally without refetching from API
      // Note: WebSocket prices are always in USD, so we need to convert them
      usePortfolioStore.getState().updatePortfolioWithNewPrice(symbol, price, exchangeRates)
    } catch (error) {
      console.error('❌ Error handling price update:', error)
    }
  }, [])

  const handleAlertTriggered = useCallback((message: AlertTriggeredMessage) => {
    console.log('🚨 Alert triggered:', message.data)
    
    // Show notification (you can integrate with a toast library)
    const alertData = message.data.alert
    if (alertData.message) {
      // You can replace this with a proper notification system
      window.alert(alertData.message)
    }
    
    // Refresh alerts and history
    fetchAlerts()
    fetchHistory()
  }, [fetchAlerts, fetchHistory])

  // Auto-connect on mount
  useEffect(() => {
    connect()
    
    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  const setExchangeRates = useCallback((rates: Record<string, number>) => {
    exchangeRatesRef.current = rates
  }, [])

  return {
    isConnected,
    connect,
    disconnect,
    subscribeToPrices,
    subscribeToAlerts,
    setExchangeRates
  }
}
