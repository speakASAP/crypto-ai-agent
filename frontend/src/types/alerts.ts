export type AlertType = 'ABOVE' | 'BELOW'

export interface PriceAlert {
  id: number
  symbol: string
  alert_type: AlertType
  threshold_price: number
  message?: string
  is_active: boolean
  created_at: string
  updated_at: string
  // New USD-based fields for calculations
  threshold_price_usd?: number
  base_currency?: string
  exchange_rate_at_creation?: number
}

export interface PriceAlertCreate {
  symbol: string
  alert_type: AlertType
  threshold_price: number
  message?: string
  is_active?: boolean
  base_currency?: string
}

export interface PriceAlertUpdate {
  symbol?: string
  alert_type?: AlertType
  threshold_price?: number
  message?: string
  is_active?: boolean
}

export interface AlertHistory {
  id: number
  alert_id: number
  symbol: string
  triggered_price: number
  threshold_price: number
  alert_type: AlertType
  message?: string
  triggered_at: string
}

export interface AlertTrigger {
  symbol: string
  current_price: number
  threshold_price: number
  alert_type: AlertType
  message?: string
}
