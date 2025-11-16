export interface AIPrediction {
  id: number
  symbol: string
  prediction_type: '24h' | 'week' | 'month' | 'year'
  predicted_price: number
  confidence_percent: number
  prediction_reasoning?: string
  model_name: string
  created_at: string
  is_verified: boolean
  actual_price_at_target?: number
  accuracy_percent?: number
}

export interface PredictionResponse {
  symbol: string
  predictions: {
    '24h'?: PredictionData
    week?: PredictionData
    month?: PredictionData
    year?: PredictionData
  }
}

export interface PredictionData {
  predicted_price: number
  confidence_percent: number
  reasoning?: string
  model_name?: string
  created_at?: string
  is_verified?: boolean
}

export interface NewsAnalysis {
  id: number
  symbol: string
  news_date: string
  title: string
  summary?: string
  sentiment_score?: number
  relevance_score?: number
  source?: string
  created_at: string
}

export interface ChartDataPoint {
  timestamp: number
  price: number
  date: string
}

export interface ChartData {
  symbol: string
  data: ChartDataPoint[]
}

export interface PerformanceStats {
  total_predictions: number
  average_accuracy: number
  by_model: Record<string, { count: number; avg_accuracy: number }>
  by_symbol: Record<string, { count: number; avg_accuracy: number }>
}
