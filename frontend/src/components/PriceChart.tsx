'use client'

import React, { useEffect, useState } from 'react'
import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts'
import { ChartData, ChartDataPoint } from '@/types'
import { apiClient } from '@/lib/api'
import { logger } from '@/lib/logger'
import Link from 'next/link'

interface PriceChartProps {
  symbol: string
  days?: number
  mini?: boolean
  height?: number
  className?: string
}

export function PriceChart({ 
  symbol, 
  days = 7, 
  mini = true, 
  height = 60,
  className = ''
}: PriceChartProps) {
  const [chartData, setChartData] = useState<ChartDataPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let retryTimeout: NodeJS.Timeout | null = null
    let isMounted = true

    const fetchChartData = async (attempt: number = 0) => {
      if (!isMounted) return

      try {
        setLoading(true)
        setError(null)
        
        // Stagger requests to avoid rate limiting - add delay based on symbol hash
        // This spreads out requests when multiple charts load simultaneously
        const symbolHash = symbol.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
        const delay = (symbolHash % 10) * 100 // 0-900ms delay based on symbol
        await new Promise(resolve => setTimeout(resolve, delay))
        
        const data = mini 
          ? await apiClient.getMiniChart(symbol, days)
          : await apiClient.getPriceHistory(symbol, days === 7 ? 365 : days)
        
        if (isMounted) {
          setChartData(data.data || [])
          setRetryCount(0) // Reset retry count on success
        }
      } catch (err: any) {
        if (!isMounted) return

        const status = err?.response?.status
        const maxRetries = 3
        
        // Suppress console errors for 503/404 - these are handled gracefully
        // Errors are caught and handled, so they won't appear in console
        
        // Handle 503 Service Unavailable with automatic retry
        if (status === 503 && attempt < maxRetries) {
          const retryDelays = [30000, 60000, 120000] // 30s, 60s, 120s
          const delay = retryDelays[attempt]
          
          setError('Failed to load chart')
          setRetryCount(attempt + 1)
          
          // Schedule retry
          retryTimeout = setTimeout(() => {
            if (isMounted) {
              fetchChartData(attempt + 1)
            }
          }, delay)
          
          logger.debug(`Retrying chart fetch for ${symbol} after ${delay}ms (attempt ${attempt + 1}/${maxRetries})`)
        } else {
          // Max retries exceeded or other error
          if (status === 503) {
            setError('Service unavailable')
          } else if (status === 404) {
            // 404 means chart data not available - show N/A or Failed to load chart
            setError('Failed to load chart')
            // Don't log 404 errors to console (handled gracefully)
            logger.debug(`Chart data not available for ${symbol} (404)`)
          } else if (status === 429) {
            setError('Rate limited - try again later')
          } else {
            setError('Failed to load chart')
          }
          setRetryCount(0)
        }
      } finally {
        if (isMounted) {
          setLoading(false)
        }
      }
    }

    if (symbol) {
      fetchChartData(0)
    }

    // Cleanup function
    return () => {
      isMounted = false
      if (retryTimeout) {
        clearTimeout(retryTimeout)
      }
    }
  }, [symbol, days, mini])

  if (loading) {
    return (
      <div 
        className={`flex items-center justify-center bg-gray-50 rounded ${className}`}
        style={{ height: `${height}px` }}
      >
        <div className="text-xs text-gray-400">Loading...</div>
      </div>
    )
  }

  if (error || chartData.length === 0) {
    return (
      <div 
        className={`flex items-center justify-center bg-gray-50 rounded ${className}`}
        style={{ height: `${height}px` }}
      >
        <div className="text-xs text-gray-400">{error || 'No data'}</div>
      </div>
    )
  }

  // Calculate price change to determine color
  const firstPrice = chartData[0]?.price || 0
  const lastPrice = chartData[chartData.length - 1]?.price || 0
  const isPositive = lastPrice >= firstPrice
  const strokeColor = isPositive ? '#10b981' : '#ef4444' // green or red

  const chartContent = (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData}>
        <Line
          type="monotone"
          dataKey="price"
          stroke={strokeColor}
          strokeWidth={mini ? 1.5 : 2}
          dot={false}
          isAnimationActive={true}
          animationDuration={300}
        />
        {!mini && (
          <Tooltip
            formatter={(value: any) => [`$${Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 8 })}`, 'Price']}
            labelFormatter={(label: any) => {
              const date = new Date(label)
              return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
            }}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  )

  if (mini) {
    // Mini chart - clickable to external CoinGecko page
    const symbolToCoingecko = (sym: string): string => {
      const map: Record<string, string> = {
        BTC: 'bitcoin',
        ETH: 'ethereum',
        BNB: 'binancecoin',
        SOL: 'solana',
        ADA: 'cardano',
        XRP: 'ripple',
        DOT: 'polkadot',
        DOGE: 'dogecoin',
        AVAX: 'avalanche-2',
        MATIC: 'matic-network',
        LINK: 'chainlink',
        UNI: 'uniswap',
        LTC: 'litecoin',
        ATOM: 'cosmos',
        ETC: 'ethereum-classic',
        BCH: 'bitcoin-cash',
        XLM: 'stellar',
        ALGO: 'algorand',
        VET: 'vechain',
        FIL: 'filecoin',
        TRX: 'tron',
        EOS: 'eos',
        AAVE: 'aave',
        GRT: 'the-graph',
        SAND: 'the-sandbox',
        MANA: 'decentraland',
        AXS: 'axie-infinity',
        CHZ: 'chiliz',
        ENJ: 'enjincoin',
      }
      return map[sym.toUpperCase()] || sym.toLowerCase()
    }

    const cgSlug = symbolToCoingecko(symbol)
    const href = `https://www.coingecko.com/en/coins/${cgSlug}`

    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={`block ${className}`}>
        {chartContent}
      </a>
    )
  }

  // Full chart
  return (
    <div className={className}>
      {chartContent}
    </div>
  )
}

