'use client'

import React, { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PredictionResponse, PredictionData } from '@/types'
import { apiClient } from '@/lib/api'
import { logger } from '@/lib/logger'
import { formatCurrency } from '@/lib/currencyUtils'
import { Sparkles, TrendingUp, TrendingDown, AlertCircle } from 'lucide-react'

interface AIAdvisorCardProps {
  symbol: string
  currentPrice?: number
  className?: string
}

export function AIAdvisorCard({ symbol, currentPrice, className = '' }: AIAdvisorCardProps) {
  const [predictions, setPredictions] = useState<PredictionResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchPredictions = async () => {
      try {
        setLoading(true)
        setError(null)
        const data = await apiClient.getAIPredictions(symbol)
        setPredictions(data)
      } catch (err: any) {
        logger.error(`Error fetching predictions for ${symbol}:`, err)
        if (err.response?.status === 404) {
          setError('No predictions available yet')
        } else {
          setError('Failed to load predictions')
        }
      } finally {
        setLoading(false)
      }
    }

    if (symbol) {
      fetchPredictions()
    }
  }, [symbol])

  const getPredictionDisplay = (predType: '24h' | 'week' | 'month' | 'year', pred?: PredictionData) => {
    if (!pred || !currentPrice) return null

    const predictedPrice = pred.predicted_price
    const changePercent = ((predictedPrice - currentPrice) / currentPrice) * 100
    const confidence = pred.confidence_percent || 0
    const isPositive = changePercent >= 0

    return {
      type: predType,
      predictedPrice,
      changePercent,
      confidence,
      isPositive,
      reasoning: pred.reasoning,
    }
  }

  if (loading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            AI Predictions
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-gray-500">Loading predictions...</div>
        </CardContent>
      </Card>
    )
  }

  if (error || !predictions) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            AI Predictions
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-gray-500 flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            {error || 'No predictions available'}
          </div>
          <button
            onClick={async () => {
              try {
                await apiClient.generatePredictions(symbol)
                // Refetch predictions
                const data = await apiClient.getAIPredictions(symbol)
                setPredictions(data)
              } catch (err) {
                logger.error('Error generating predictions:', err)
              }
            }}
            className="mt-2 text-xs text-blue-600 hover:text-blue-800"
          >
            Generate Predictions
          </button>
        </CardContent>
      </Card>
    )
  }

  const pred24h = getPredictionDisplay('24h', predictions.predictions['24h'])
  const predWeek = getPredictionDisplay('week', predictions.predictions.week)
  const predMonth = getPredictionDisplay('month', predictions.predictions.month)
  const predYear = getPredictionDisplay('year', predictions.predictions.year)

  const predictionsList = [pred24h, predWeek, predMonth, predYear].filter(Boolean)

  if (predictionsList.length === 0) {
    return null
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Sparkles className="h-4 w-4" />
          AI Predictions
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {predictionsList.map((pred) => {
          if (!pred) return null

          const timeLabel = 
            pred.type === '24h' ? '24h' :
            pred.type === 'week' ? '1 Week' :
            pred.type === 'month' ? '1 Month' :
            '1 Year'

          return (
            <div key={pred.type} className="border-b pb-2 last:border-0">
              <div className="flex justify-between items-start mb-1">
                <span className="text-xs font-medium text-gray-600">{timeLabel}</span>
                <div className="flex items-center gap-2">
                  {pred.isPositive ? (
                    <TrendingUp className="h-3 w-3 text-green-600" />
                  ) : (
                    <TrendingDown className="h-3 w-3 text-red-600" />
                  )}
                  <span className={`text-xs font-semibold ${pred.isPositive ? 'text-green-600' : 'text-red-600'}`}>
                    {pred.changePercent >= 0 ? '+' : ''}{pred.changePercent.toFixed(2)}%
                  </span>
                </div>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-500">
                  {formatCurrency(pred.predictedPrice, 'USD')}
                </span>
                <span className="text-xs text-gray-400">
                  {pred.confidence.toFixed(0)}% confidence
                </span>
              </div>
              {pred.reasoning && (
                <p className="text-xs text-gray-500 mt-1 line-clamp-2">{pred.reasoning}</p>
              )}
            </div>
          )
        })}
        <div className="text-xs text-gray-400 pt-2 border-t">
          Model: {predictions.predictions['24h']?.model_name || 'N/A'}
        </div>
      </CardContent>
    </Card>
  )
}

