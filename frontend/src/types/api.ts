export interface ApiResponse<T> {
  data: T
  message?: string
  success: boolean
}

export interface ApiError {
  message: string
  status: number
  details?: any
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  limit: number
  hasNext: boolean
  hasPrev: boolean
}

export interface WebSocketMessage {
  type: 'price_update' | 'alert_triggered' | 'connection_status'
  data: any
  timestamp: string
}

export interface PriceUpdateMessage extends WebSocketMessage {
  type: 'price_update'
  data: {
    symbol: string
    price: number
    timestamp: string
  }
}

export interface AlertTriggeredMessage extends WebSocketMessage {
  type: 'alert_triggered'
  data: {
    alert: {
      id: number
      symbol: string
      alert_type: string
      threshold_price: number
      message?: string
    }
  }
}
