export interface TrackedSymbol {
  symbol: string
  is_active: boolean
  created_at: string
}

export interface TrackedSymbolCreate {
  symbol: string
  is_active?: boolean
}

export interface TrackedSymbolUpdate {
  is_active?: boolean
}

export interface CryptoSymbol {
  id: number
  symbol: string
  name?: string
  description?: string
  is_tradable: boolean
  last_updated: string
}

export interface CryptoSymbolCreate {
  symbol: string
  name?: string
  description?: string
  is_tradable?: boolean
}

export interface CryptoSymbolUpdate {
  name?: string
  description?: string
  is_tradable?: boolean
}

export interface SymbolPrice {
  symbol: string
  price: number
  timestamp: string
}
