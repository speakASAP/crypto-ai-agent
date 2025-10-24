import { useWebSocketContext } from '@/contexts/WebSocketContext'

interface WebSocketHook {
  isConnected: boolean
  connectionState: 'disconnected' | 'connecting' | 'connected' | 'reconnecting'
  connect: () => void
  disconnect: () => void
  subscribeToPrices: (symbols: string[]) => void
  subscribeToAlerts: () => void
  setExchangeRates: (rates: Record<string, number>) => void
}

export const useWebSocket = (): WebSocketHook => {
  const context = useWebSocketContext()
  
  return {
    isConnected: context.isConnected,
    connectionState: context.connectionState,
    connect: context.connect,
    disconnect: context.disconnect,
    subscribeToPrices: context.subscribeToPrices,
    subscribeToAlerts: context.subscribeToAlerts,
    setExchangeRates: context.setExchangeRates
  }
}
