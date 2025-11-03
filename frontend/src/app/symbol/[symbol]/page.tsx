'use client'

import React, { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { PriceChart } from '@/components/PriceChart'
import { AIAdvisorCard } from '@/components/AIAdvisorCard'
import { ArrowLeft, TrendingUp, TrendingDown, Newspaper, BarChart3 } from 'lucide-react'
import { apiClient } from '@/lib/api'
import { formatCurrency } from '@/lib/currencyUtils'
import { logger } from '@/lib/logger'
import { ChartData, PredictionResponse, NewsAnalysis, PerformanceStats } from '@/types'
import Link from 'next/link'

export default function SymbolDetailPage() {
  const params = useParams()
  const router = useRouter()
  const symbol = (params.symbol as string)?.toUpperCase() || ''

  const [chartData, setChartData] = useState<ChartData | null>(null)
  const [predictions, setPredictions] = useState<PredictionResponse | null>(null)
  const [news, setNews] = useState<NewsAnalysis[]>([])
  const [performance, setPerformance] = useState<PerformanceStats | null>(null)
  const [currentPrice, setCurrentPrice] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!symbol) return

    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)

        // Fetch all data in parallel
        const [chart, preds, newsData, perf, priceData] = await Promise.allSettled([
          apiClient.getPriceHistory(symbol, 365),
          apiClient.getAIPredictions(symbol),
          apiClient.getAINews(symbol, 7),
          apiClient.getAIPerformance(symbol),
          apiClient.getSymbolPrices(symbol),
        ])

        if (chart.status === 'fulfilled') {
          setChartData(chart.value)
        }

        if (preds.status === 'fulfilled') {
          setPredictions(preds.value)
        } else if (preds.status === 'rejected' && preds.reason?.response?.status !== 404) {
          logger.error('Error fetching predictions:', preds.reason)
        }

        if (newsData.status === 'fulfilled') {
          setNews(newsData.value)
        }

        if (perf.status === 'fulfilled') {
          setPerformance(perf.value)
        }

        if (priceData.status === 'fulfilled' && priceData.value.length > 0) {
          setCurrentPrice(priceData.value[0].price)
        }

      } catch (err: any) {
        logger.error(`Error fetching data for ${symbol}:`, err)
        setError('Failed to load symbol data')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [symbol])

  const handleGeneratePredictions = async () => {
    try {
      await apiClient.generatePredictions(symbol)
      const newPredictions = await apiClient.getAIPredictions(symbol)
      setPredictions(newPredictions)
    } catch (err: any) {
      logger.error('Error generating predictions:', err)
    }
  }

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Loading {symbol} data...</p>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Button onClick={() => router.back()} variant="outline" className="mb-4">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-red-600">{error}</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      {/* Header */}
      <div className="mb-6">
        <Button onClick={() => router.back()} variant="outline" className="mb-4">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Portfolio
        </Button>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">{symbol}</h1>
            {currentPrice && (
              <p className="text-xl text-gray-600 mt-2">
                {formatCurrency(currentPrice, 'USD')}
              </p>
            )}
          </div>
          <Button onClick={handleGeneratePredictions} variant="outline">
            Regenerate Predictions
          </Button>
        </div>
      </div>

      {/* Main Chart */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Price History (1 Year)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {chartData && chartData.data.length > 0 ? (
            <div className="h-96">
              <PriceChart symbol={symbol} days={365} mini={false} height={384} />
            </div>
          ) : (
            <div className="h-96 flex items-center justify-center text-gray-400">
              No chart data available
            </div>
          )}
        </CardContent>
      </Card>

      {/* Predictions and Performance Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* AI Predictions */}
        <div>
          <AIAdvisorCard 
            symbol={symbol} 
            currentPrice={currentPrice || undefined}
            className="h-full"
          />
        </div>

        {/* Performance Statistics */}
        <Card>
          <CardHeader>
            <CardTitle>Prediction Performance</CardTitle>
          </CardHeader>
          <CardContent>
            {performance && performance.total_predictions > 0 ? (
              <div className="space-y-4">
                <div>
                  <div className="text-sm text-gray-600 mb-1">Total Verified Predictions</div>
                  <div className="text-2xl font-bold">{performance.total_predictions}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-600 mb-1">Average Accuracy</div>
                  <div className="text-2xl font-bold text-green-600">
                    {performance.average_accuracy.toFixed(1)}%
                  </div>
                </div>
                {Object.keys(performance.by_model).length > 0 && (
                  <div>
                    <div className="text-sm text-gray-600 mb-2">By Model</div>
                    <div className="space-y-2">
                      {Object.entries(performance.by_model).map(([model, stats]) => (
                        <div key={model} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                          <span className="text-sm font-medium">{model}</span>
                          <div className="text-right">
                            <div className="text-sm text-gray-600">{stats.count} predictions</div>
                            <div className="text-sm font-semibold text-green-600">
                              {stats.avg_accuracy.toFixed(1)}% accuracy
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center text-gray-500 py-8">
                <p>No performance data available yet</p>
                <p className="text-sm mt-2">Predictions need to be verified to show performance</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* News Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Newspaper className="h-5 w-5" />
            Recent News ({news.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {news.length > 0 ? (
            <div className="space-y-4">
              {news.map((article, index) => (
                <div key={index} className="border-b pb-4 last:border-0">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <h3 className="font-semibold text-lg mb-1">{article.title}</h3>
                      {article.summary && (
                        <p className="text-sm text-gray-600 mb-2">{article.summary}</p>
                      )}
                      <div className="flex items-center gap-4 text-xs text-gray-500">
                        {article.source && <span>{article.source}</span>}
                        {article.news_date && (
                          <span>{new Date(article.news_date).toLocaleDateString()}</span>
                        )}
                      </div>
                    </div>
                    {article.sentiment_score !== undefined && (
                      <div className="flex items-center gap-2 ml-4">
                        {article.sentiment_score >= 0.3 ? (
                          <TrendingUp className="h-5 w-5 text-green-600" />
                        ) : article.sentiment_score <= -0.3 ? (
                          <TrendingDown className="h-5 w-5 text-red-600" />
                        ) : (
                          <div className="h-5 w-5 rounded-full bg-gray-300" />
                        )}
                        <div className="text-sm font-medium">
                          {article.sentiment_score > 0 ? '+' : ''}
                          {(article.sentiment_score * 100).toFixed(0)}%
                        </div>
                      </div>
                    )}
                  </div>
                  {article.relevance_score !== undefined && (
                    <div className="text-xs text-gray-400 mt-2">
                      Relevance: {(article.relevance_score * 100).toFixed(0)}%
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-gray-500 py-8">
              <Newspaper className="h-12 w-12 mx-auto mb-4 text-gray-300" />
              <p>No recent news found for {symbol}</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

