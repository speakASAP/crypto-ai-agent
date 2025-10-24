'use client'

import React, { createContext, useContext, useRef, useCallback, useState, useEffect } from 'react'
import { usePortfolioStore } from '@/stores/portfolioStore'
import { useAlertsStore } from '@/stores/alertsStore'
import { useSymbolsStore } from '@/stores/symbolsStore'
import { PriceUpdateMessage, AlertTriggeredMessage } from '@/types'

interface WebSocketContextType {
  isConnected: boolean
  connectionState: 'disconnected' | 'connecting' | 'connected' | 'reconnecting'
  connect: () => void
  disconnect: () => void
  subscribeToPrices: (symbols: string[]) => void
  subscribeToAlerts: () => void
  setExchangeRates: (rates: Record<string, number>) => void
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined)

interface WebSocketProviderProps {
  children: React.ReactNode
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({ children }) => {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const isMountedRef = useRef(true)
  const [isConnected, setIsConnected] = useState(false)
  const [connectionState, setConnectionState] = useState<'disconnected' | 'connecting' | 'connected' | 'reconnecting'>('disconnected')
  const exchangeRatesRef = useRef<Record<string, number>>({})
  
  const { fetchPortfolio, fetchSummary } = usePortfolioStore()
  const { fetchAlerts, fetchHistory } = useAlertsStore()
  const { fetchSymbolPrices } = useSymbolsStore()

  const getReconnectDelay = useCallback((attempt: number): number => {
    if (attempt <= 3) {
      // Exponential backoff: 1s, 2s, 4s
      return Math.pow(2, attempt - 1) * 1000
    } else {
      // Fallback to 5-second intervals
      return 5000
    }
  }, [])

  const connect = useCallback(() => {
    if (!isMountedRef.current) return
    
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      console.log('WebSocket already connected or connecting, skipping...')
      return
    }

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws'
    console.log(`🔌 [${new Date().toISOString()}] Connecting to WebSocket:`, wsUrl)
    console.log(`📊 [${new Date().toISOString()}] Reconnect attempt: ${reconnectAttemptsRef.current + 1}`)
    
    setConnectionState('connecting')

    try {
      // Clean up any existing connection
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }

      wsRef.current = new WebSocket(wsUrl)

      wsRef.current.onopen = () => {
        if (!isMountedRef.current || !wsRef.current) {
          console.log('🔧 WebSocket opened but component unmounted or ref null, ignoring...')
          return
        }
        
        console.log(`✅ [${new Date().toISOString()}] WebSocket connected successfully`)
        setIsConnected(true)
        setConnectionState('connected')
        reconnectAttemptsRef.current = 0 // Reset attempts on successful connection
        
        // Clear any pending reconnection
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current)
          reconnectTimeoutRef.current = null
        }
        
        // Send initial connection message
        try {
          wsRef.current?.send(JSON.stringify({
            type: 'connect',
            data: 'Client connected'
          }))
          console.log('📤 Sent initial connection message')
        } catch (error) {
          console.error('❌ Failed to send initial connection message:', error)
        }
      }

      wsRef.current.onmessage = (event) => {
        if (!isMountedRef.current) return
        
        try {
          const message = JSON.parse(event.data)
          handleWebSocketMessage(message)
        } catch (error) {
          console.error('❌ Failed to parse WebSocket message:', error)
          console.error('❌ Raw message data:', event.data)
        }
      }

      wsRef.current.onclose = (event) => {
        if (!isMountedRef.current) {
          console.log('🔧 WebSocket closed but component unmounted, ignoring...')
          return
        }
        
        console.log(`🔌 [${new Date().toISOString()}] WebSocket disconnected:`, {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean,
          readyState: wsRef.current?.readyState
        })
        setIsConnected(false)
        setConnectionState('disconnected')
        
        // Attempt to reconnect after delay
        if (event.code !== 1000 && isMountedRef.current) { // Not a normal closure
          const delay = getReconnectDelay(reconnectAttemptsRef.current + 1)
          reconnectAttemptsRef.current += 1
          
          console.log(`🔄 [${new Date().toISOString()}] Scheduling reconnection in ${delay}ms (attempt ${reconnectAttemptsRef.current})`)
          setConnectionState('reconnecting')
          
          reconnectTimeoutRef.current = setTimeout(() => {
            if (isMountedRef.current) {
              console.log(`🔄 [${new Date().toISOString()}] Attempting to reconnect...`)
              connect()
            }
          }, delay)
        } else {
          console.log('🔧 WebSocket closed normally or component unmounted, not reconnecting')
        }
      }

      wsRef.current.onerror = (error) => {
        if (!isMountedRef.current) return
        
        console.error(`❌ [${new Date().toISOString()}] WebSocket error:`, error)
        console.error('WebSocket readyState:', wsRef.current?.readyState)
        console.error('WebSocket URL:', wsUrl)
        console.error('WebSocket error details:', {
          type: error.type,
          target: error.target,
          currentTarget: error.currentTarget
        })
        setIsConnected(false)
        setConnectionState('disconnected')
      }
    } catch (error) {
      if (!isMountedRef.current) return
      console.error(`❌ [${new Date().toISOString()}] Failed to create WebSocket connection:`, error)
      setConnectionState('disconnected')
    }
  }, [getReconnectDelay])

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
    setConnectionState('disconnected')
    reconnectAttemptsRef.current = 0
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
      case 'ping':
        // Respond to ping with pong to keep connection alive
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({
            type: 'pong',
            data: 'Client alive'
          }))
        }
        break
      default:
        console.log('📨 Unknown message type:', message.type)
    }
  }, [])

  const handlePriceUpdate = useCallback((message: PriceUpdateMessage, exchangeRates?: Record<string, number>) => {
    try {
      console.log('📈 Price update:', message.data)
      
      // Update symbol prices in store
      const { symbol, price, timestamp, timestamp_formatted } = message.data as any
      const symbolsStore = useSymbolsStore.getState()
      symbolsStore.symbolPrices[symbol] = {
        symbol,
        price,
        timestamp
      }
      
      // Update portfolio values locally without refetching from API
      // Note: WebSocket prices are always in USD, so we need to convert them
      usePortfolioStore.getState().updatePortfolioWithNewPrice(symbol, price, exchangeRates)
      
      // Log the timestamp for debugging
      if (timestamp_formatted) {
        console.log(`📅 Price updated for ${symbol} at ${timestamp_formatted}`)
      }
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
    console.log('🔧 WebSocketProvider mounted, setting up connection...')
    isMountedRef.current = true
    
    // Add a delay to prevent race conditions and allow React to stabilize
    const connectTimeout = setTimeout(() => {
      if (isMountedRef.current) {
        console.log('🔧 Timeout reached, attempting connection...')
        connect()
      } else {
        console.log('🔧 Component unmounted before connection timeout')
      }
    }, 500) // Increased delay to 500ms
    
    return () => {
      console.log('🔧 WebSocketProvider unmounting, cleaning up...')
      isMountedRef.current = false
      clearTimeout(connectTimeout)
      disconnect()
    }
  }, []) // No dependencies to prevent re-creation

  const setExchangeRates = useCallback((rates: Record<string, number>) => {
    exchangeRatesRef.current = rates
  }, [])

  const value: WebSocketContextType = {
    isConnected,
    connectionState,
    connect,
    disconnect,
    subscribeToPrices,
    subscribeToAlerts,
    setExchangeRates
  }

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  )
}

export const useWebSocketContext = (): WebSocketContextType => {
  const context = useContext(WebSocketContext)
  if (context === undefined) {
    throw new Error('useWebSocketContext must be used within a WebSocketProvider')
  }
  return context
}
