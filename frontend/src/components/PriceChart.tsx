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

  useEffect(() => {
    const fetchChartData = async () => {
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
        
        setChartData(data.data || [])
      } catch (err: any) {
        logger.error(`Error fetching chart data for ${symbol}:`, err)
        // Check if it's a rate limit or API error
        if (err?.response?.status === 404 || err?.response?.status === 429) {
          setError('Rate limited - try again later')
        } else {
          setError('Failed to load chart')
        }
      } finally {
        setLoading(false)
      }
    }

    if (symbol) {
      fetchChartData()
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

