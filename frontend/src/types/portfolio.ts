export interface PortfolioItem {
  id: number
  symbol: string
  amount: number
  price_buy: number
  purchase_date?: string
  base_currency: string
  purchase_price_eur?: number
  purchase_price_czk?: number
  source?: string
  commission: number
  total_investment_text?: string
  created_at: string
  updated_at: string
  current_price?: number
  current_value?: number
  pnl?: number
  pnl_percent?: number
  // New USD-based fields for calculations
  price_buy_usd?: number
  commission_usd?: number
  current_price_usd?: number
  current_value_usd?: number
  pnl_usd?: number
  pnl_percent_usd?: number
  exchange_rate_at_purchase?: number
}

export interface PortfolioCreate {
  symbol: string
  amount: number
  price_buy: number
  purchase_date?: string
  base_currency: string
  source?: string
  commission?: number
  total_investment_text?: string
}

export interface PortfolioUpdate {
  symbol?: string
  amount?: number
  price_buy?: number
  purchase_date?: string
  base_currency?: string
  source?: string
  commission?: number
  total_investment_text?: string
}

export interface PortfolioSummary {
  total_value: number
  total_invested: number
  total_pnl: number
  total_pnl_percent: number
  currency: string
  item_count: number
}

export type Currency = 'USD' | 'EUR' | 'CZK'
