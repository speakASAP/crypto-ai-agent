'use client'

import React, { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PredictionResponse, PredictionData } from '@/types'
import { apiClient } from '@/lib/api'
import { logger } from '@/lib/logger'
import { formatCurrency } from '@/lib/currencyUtils'
import { Sparkles, TrendingUp, TrendingDown, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react'

// Helper function to render markdown links in reasoning text as external links
function renderReasoningWithLinks(text: string) {
  if (!text) return null
  
  // Split by newlines to handle multi-line reasoning with sources section
  const lines = text.split('\n')
  const processedLines: (string | JSX.Element)[] = []
  let key = 0
  
  lines.forEach((line) => {
    // Match markdown links: [1](url), [2](url), etc.
    const linkPattern = /\[(\d+)\]\(([^)]+)\)/g
    const parts: (string | JSX.Element)[] = []
    let lastIndex = 0
    let match
    
    while ((match = linkPattern.exec(line)) !== null) {
      // Add text before the link
      if (match.index > lastIndex) {
        parts.push(line.substring(lastIndex, match.index))
      }
      
      // Add the external link
      const linkNum = match[1]
      const url = match[2]
      
      // Ensure URL is absolute
      const externalUrl = url.startsWith('http://') || url.startsWith('https://') 
        ? url 
        : `https://${url}`
      
      parts.push(
        <a
          key={key++}
          href={externalUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:text-blue-800 underline font-medium"
          onClick={(e) => e.stopPropagation()}
        >
          [{linkNum}]
        </a>
      )
      lastIndex = match.index + match[0].length
    }
    
    // Add remaining text
    if (lastIndex < line.length) {
      parts.push(line.substring(lastIndex))
    }
    
    if (parts.length > 0) {
      processedLines.push(<span key={key++}>{parts}</span>)
    } else if (line.trim()) {
      processedLines.push(<span key={key++}>{line}</span>)
    }
  })
  
  return processedLines.length > 0 
    ? <div>{processedLines.map((line, idx) => <div key={idx}>{line}</div>)}</div>
    : <span>{text}</span>
}

interface AIAdvisorCardProps {
  symbol: string
  currentPrice?: number
  className?: string
}

export function AIAdvisorCard({ symbol, currentPrice, className = '' }: AIAdvisorCardProps) {
  const [predictions, setPredictions] = useState<PredictionResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isExpanded, setIsExpanded] = useState(false)

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
    
    // Skip predictions where predicted price equals current price (no meaningful prediction)
    if (Math.abs(predictedPrice - currentPrice) < 0.0001) {
      return null
    }
    
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

  // Get predictions
  const pred24h = getPredictionDisplay('24h', predictions?.predictions['24h'])
  const predWeek = getPredictionDisplay('week', predictions?.predictions.week)
  const predMonth = getPredictionDisplay('month', predictions?.predictions.month)
  const predYear = getPredictionDisplay('year', predictions?.predictions.year)

  const predictionsList = [pred24h, predWeek, predMonth, predYear].filter(Boolean)

  // Collapsed view - show only 1-year prediction
  const renderCollapsedView = () => {
    // Prioritize 1-year prediction, fallback to longest available
    const mainPrediction = predYear || predMonth || predWeek || pred24h

    if (!mainPrediction) {
      if (loading) {
        return (
          <div className="flex items-center justify-between p-2 rounded border bg-gray-50">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-gray-400" />
              <span className="text-xs text-gray-500">Loading AI predictions...</span>
            </div>
          </div>
        )
      }

      if (error || !predictions) {
        return (
          <div className="flex items-center justify-between p-2 rounded border bg-gray-50">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-gray-400" />
              <span className="text-xs text-gray-500">{error || 'No predictions'}</span>
            </div>
            <button
              onClick={async (e) => {
                e.stopPropagation()
                try {
                  await apiClient.generatePredictions(symbol)
                  const data = await apiClient.getAIPredictions(symbol)
                  setPredictions(data)
                } catch (err) {
                  logger.error('Error generating predictions:', err)
                }
              }}
              className="text-xs text-blue-600 hover:text-blue-800"
            >
              Generate
            </button>
          </div>
        )
      }

      return null
    }

    const timeLabel = 
      mainPrediction.type === '24h' ? '24h' :
      mainPrediction.type === 'week' ? '1W' :
      mainPrediction.type === 'month' ? '1M' :
      '1Y'

    const bgColor = mainPrediction.isPositive 
      ? 'bg-green-50 border-green-200 hover:bg-green-100' 
      : 'bg-red-50 border-red-200 hover:bg-red-100'
    const textColor = mainPrediction.isPositive ? 'text-green-700' : 'text-red-700'

    return (
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={`w-full flex items-center justify-between p-3 rounded border transition-all duration-200 ${bgColor}`}
      >
        <div className="flex items-center gap-3 flex-1">
          <div className="flex items-center gap-2">
            <Sparkles className={`h-4 w-4 ${textColor}`} />
            <span className="text-xs font-medium text-gray-600">AI {timeLabel}:</span>
          </div>
          <div className="flex items-center gap-2">
            {mainPrediction.isPositive ? (
              <TrendingUp className={`h-4 w-4 ${textColor}`} />
            ) : (
              <TrendingDown className={`h-4 w-4 ${textColor}`} />
            )}
            <span className={`text-base font-bold ${textColor}`}>
              {mainPrediction.changePercent >= 0 ? '+' : ''}{mainPrediction.changePercent.toFixed(1)}%
            </span>
          </div>
          <span className="text-xs text-gray-500">
            ({mainPrediction.confidence.toFixed(0)}% confidence)
          </span>
        </div>
        {isExpanded ? (
          <ChevronUp className="h-4 w-4 text-gray-400" />
        ) : (
          <ChevronDown className="h-4 w-4 text-gray-400" />
        )}
      </button>
    )
  }

  // Expanded view - show all predictions
  const renderExpandedView = () => {
    if (!isExpanded || !predictions) return null

    return (
      <Card className={`mt-2 transition-all duration-200 ease-in-out ${className}`}>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Sparkles className="h-4 w-4" />
              AI Predictions
            </CardTitle>
            <button
              onClick={() => setIsExpanded(false)}
              className="text-xs text-gray-500 hover:text-gray-700"
            >
              Collapse
            </button>
          </div>
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
                  <span className="text-xs text-gray-400">
                    {pred.confidence.toFixed(0)}% confidence
                  </span>
                </div>
                {pred.reasoning && (
                  <div className="text-xs text-gray-500 mt-1">
                    <div className="line-clamp-3 mb-1">
                      {renderReasoningWithLinks(pred.reasoning)}
                    </div>
                  </div>
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

  if (loading && !predictions) {
    return (
      <div className={className}>
        {renderCollapsedView()}
      </div>
    )
  }

  if (error && !predictions) {
    return (
      <div className={className}>
        {renderCollapsedView()}
      </div>
    )
  }

  if (predictionsList.length === 0 && !loading && !error) {
    return null
  }

  return (
    <div className={className}>
      {renderCollapsedView()}
      {renderExpandedView()}
    </div>
  )
}
