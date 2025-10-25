'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { CryptoSearchSelect } from '@/components/CryptoSearchSelect'
import { PriceAlert, PriceAlertCreate, PriceAlertUpdate, Currency, CryptoSymbol } from '@/types'
import { apiClient } from '@/lib/api'

interface AlertModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: (alert: PriceAlertCreate | PriceAlertUpdate) => Promise<void>
  alert?: PriceAlert | null
  presetSymbol?: string
  currentPrice?: number
  selectedCurrency: Currency
  portfolioItem?: {
    amount: number
    price_buy: number
    commission?: number
    total_investment_text?: string
    current_value?: number
    pnl?: number
    pnl_percent?: number
  }
  availableSymbols?: string[]
}

// Utility function to format numbers with spaces for thousands
const formatNumberWithSpaces = (value: number | string): string => {
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '0'
  
  // Split by decimal point
  const parts = num.toString().split('.')
  const integerPart = parts[0]
  const decimalPart = parts[1] ? '.' + parts[1] : ''
  
  // Add spaces every 3 digits from the right
  const formattedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
  
  return formattedInteger + decimalPart
}

// Utility function to parse formatted number back to number
const parseFormattedNumber = (value: string): number => {
  return parseFloat(value.replace(/\s/g, ''))
}

export function AlertModal({ isOpen, onClose, onSave, alert, presetSymbol, currentPrice, selectedCurrency, portfolioItem, availableSymbols = [] }: AlertModalProps) {
  const [formData, setFormData] = useState({
    symbol: '',
    threshold_price: '',
    alert_type: 'ABOVE',
    message: ''
  })

  const [loading, setLoading] = useState(false)
  const [thresholdPrice, setThresholdPrice] = useState(0)
  const [priceRange, setPriceRange] = useState({ min: 0, max: 0 })
  const [selectedSymbol, setSelectedSymbol] = useState('')
  const [selectedCurrentPrice, setSelectedCurrentPrice] = useState(0)
  const [loadingPrice, setLoadingPrice] = useState(false)
  const [selectedCryptoSymbol, setSelectedCryptoSymbol] = useState<CryptoSymbol | null>(null)
  const [formattedThresholdPrice, setFormattedThresholdPrice] = useState('')
  const [exchangeRates, setExchangeRates] = useState<Record<string, number>>({})

  // Function to load exchange rates
  const loadExchangeRates = async () => {
    try {
      const rates = await apiClient.getExchangeRates()
      setExchangeRates(rates.rates)
    } catch (error) {
      console.error('Failed to load exchange rates:', error)
    }
  }

  // Function to convert USD price to selected currency
  const convertToCurrency = (usdPrice: number, targetCurrency: string): number => {
    if (targetCurrency === 'USD') return usdPrice
    if (!exchangeRates[targetCurrency]) return usdPrice
    return usdPrice * exchangeRates[targetCurrency]
  }

  // Function to fetch current price for selected symbol
  const fetchCurrentPrice = async (symbol: string) => {
    if (!symbol) return
    
    setLoadingPrice(true)
    try {
      const data = await apiClient.getSymbolPrice(symbol)
      const usdPrice = data.price
      
      // Convert USD price to selected currency
      const convertedPrice = convertToCurrency(usdPrice, selectedCurrency)
      
      setSelectedCurrentPrice(convertedPrice)
      setThresholdPrice(convertedPrice)
      setFormattedThresholdPrice(formatNumberWithSpaces(convertedPrice))
      setFormData(prev => ({ 
        ...prev, 
        threshold_price: convertedPrice.toString() 
      }))
      // Set price range to ±50% of current price
      const range = convertedPrice * 0.5
      setPriceRange({
        min: Math.max(0, convertedPrice - range),
        max: convertedPrice + range
      })
    } catch (error) {
      console.error('Failed to fetch current price:', error)
      // Set default values on error
      setSelectedCurrentPrice(0)
      setThresholdPrice(0)
      setFormattedThresholdPrice('0')
      setFormData(prev => ({ 
        ...prev, 
        threshold_price: '0' 
      }))
      setPriceRange({ min: 0, max: 100000 }) // Default range
    } finally {
      setLoadingPrice(false)
    }
  }

  useEffect(() => {
    if (alert) {
      setFormData({
        symbol: alert.symbol,
        threshold_price: alert.threshold_price.toString(),
        alert_type: alert.alert_type,
        message: alert.message || ''
      })
      setThresholdPrice(alert.threshold_price)
      setSelectedSymbol(alert.symbol)
      setSelectedCurrentPrice(0) // We don't have current price for editing
    } else if (presetSymbol && currentPrice) {
      setFormData({
        symbol: presetSymbol,
        threshold_price: currentPrice.toString(),
        alert_type: 'ABOVE',
        message: ''
      })
      setThresholdPrice(currentPrice)
      setSelectedSymbol(presetSymbol)
      setSelectedCurrentPrice(currentPrice)
      setFormattedThresholdPrice(formatNumberWithSpaces(currentPrice))
      // Set price range to ±50% of current price
      const range = currentPrice * 0.5
      setPriceRange({
        min: Math.max(0, currentPrice - range),
        max: currentPrice + range
      })
    } else {
      // Reset for new alert creation
      setFormData({
        symbol: '',
        threshold_price: '',
        alert_type: 'ABOVE',
        message: ''
      })
      setThresholdPrice(0)
      setPriceRange({ min: 0, max: 0 })
      setSelectedSymbol('')
      setSelectedCurrentPrice(0)
      setFormattedThresholdPrice('')
    }
  }, [alert, presetSymbol, currentPrice, isOpen])

  // Load exchange rates when component mounts
  useEffect(() => {
    if (isOpen) {
      loadExchangeRates()
    }
  }, [isOpen])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      const data = {
        symbol: presetSymbol || selectedSymbol || formData.symbol,
        threshold_price: parseFloat(formData.threshold_price),
        alert_type: formData.alert_type as 'ABOVE' | 'BELOW',
        message: formData.message,
        base_currency: selectedCurrency
      }

      await onSave(data)
      onClose()
    } catch (error) {
      console.error('Error saving alert:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  // Currency to locale mapping for proper symbol display
  const currencyToLocale: Record<string, string> = {
    'USD': 'en-US',
    'EUR': 'de-DE', 
    'CZK': 'cs-CZ'
  }

  const formatCurrency = (amount: number) => {
    const locale = currencyToLocale[selectedCurrency] || 'en-US'
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: selectedCurrency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(amount)
  }

  const formatCurrencyRounded = (amount: number) => {
    const locale = currencyToLocale[selectedCurrency] || 'en-US'
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: selectedCurrency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(Math.round(amount))
  }

  const calculatePercentageChange = (threshold: number, current: number) => {
    if (current === 0) return 0
    return ((threshold - current) / current) * 100
  }

  const adjustThresholdByPercentage = (percentage: number) => {
    const effectiveCurrentPrice = currentPrice || selectedCurrentPrice
    if (!effectiveCurrentPrice) return
    
    const adjustment = effectiveCurrentPrice * (percentage / 100)
    const newThreshold = effectiveCurrentPrice + adjustment
    const clampedThreshold = Math.max(priceRange.min, Math.min(priceRange.max, newThreshold))
    
    setThresholdPrice(clampedThreshold)
    setFormattedThresholdPrice(formatNumberWithSpaces(clampedThreshold))
    setFormData(prev => ({ 
      ...prev, 
      threshold_price: clampedThreshold.toString() 
    }))
  }

  const handleSliderChange = (value: number) => {
    setThresholdPrice(value)
    setFormattedThresholdPrice(formatNumberWithSpaces(value))
    setFormData(prev => ({ 
      ...prev, 
      threshold_price: value.toString() 
    }))
  }

  const getSliderPosition = () => {
    if (priceRange.min === priceRange.max) return 50
    return ((thresholdPrice - priceRange.min) / (priceRange.max - priceRange.min)) * 100
  }

  const calculatePotentialPnL = () => {
    const effectiveCurrentPrice = currentPrice || selectedCurrentPrice
    if (!effectiveCurrentPrice || !thresholdPrice) return null
    
    const priceChange = thresholdPrice - effectiveCurrentPrice
    const percentageChange = (priceChange / effectiveCurrentPrice) * 100
    
    return {
      priceChange,
      percentageChange,
      isProfit: priceChange > 0
    }
  }

  const calculatePriceDifference = () => {
    const effectiveCurrentPrice = currentPrice || selectedCurrentPrice
    if (!effectiveCurrentPrice || !thresholdPrice) return null
    
    const priceChange = thresholdPrice - effectiveCurrentPrice
    const percentageChange = (priceChange / effectiveCurrentPrice) * 100
    
    return {
      priceChange,
      percentageChange,
      isAbove: priceChange > 0,
      isBelow: priceChange < 0
    }
  }

  const calculateInvestmentBasedPnL = () => {
    if (!portfolioItem || !thresholdPrice) return null
    
    const { amount, price_buy, commission, total_investment_text, current_value, pnl, pnl_percent } = portfolioItem
    const effectiveCurrentPrice = currentPrice || selectedCurrentPrice
    
    // Use the same logic as the main dashboard - use total_investment_text if available
    let totalInvestment: number
    if (total_investment_text) {
      // Parse the total_investment_text to extract the numeric value
      const match = total_investment_text.match(/[\d,.\s]+/)
      if (match) {
        totalInvestment = parseFloat(match[0].replace(/[,\s]/g, ''))
      } else {
        totalInvestment = (amount * price_buy) + (commission || 0)
      }
    } else {
      totalInvestment = (amount * price_buy) + (commission || 0)
    }
    
    const thresholdValue = amount * thresholdPrice
    
    // Use the same current value that the main dashboard uses
    const currentValue = current_value || (amount * (effectiveCurrentPrice || 0))
    
    // If we have the exact P&L from the main dashboard, use that as base
    // and calculate the difference from threshold price
    if (pnl !== undefined && pnl_percent !== undefined) {
      // Calculate what the P&L would be at the threshold price
      const currentPriceFromPnl = currentValue / amount
      const priceChange = thresholdPrice - currentPriceFromPnl
      const investmentChange = pnl + (priceChange * amount)
      const investmentPercentageChange = totalInvestment > 0 ? (investmentChange / totalInvestment) * 100 : 0
      
      return {
        investmentChange,
        investmentPercentageChange,
        isProfit: investmentChange > 0
      }
    }
    
    // Fallback to direct calculation
    const investmentChange = thresholdValue - currentValue
    const investmentPercentageChange = currentValue > 0 ? (investmentChange / currentValue) * 100 : 0
    
    return {
      investmentChange,
      investmentPercentageChange,
      isProfit: investmentChange > 0
    }
  }

  const calculateInvestmentPnL = () => {
    if (!portfolioItem) return null
    
    const effectiveCurrentPrice = currentPrice || selectedCurrentPrice
    if (!effectiveCurrentPrice) return null
    
    const { amount, price_buy, commission, total_investment_text, current_value, pnl, pnl_percent } = portfolioItem
    
    // Use the same logic as the main dashboard - use total_investment_text if available
    let totalInvestment: number
    if (total_investment_text) {
      // Parse the total_investment_text to extract the numeric value
      const match = total_investment_text.match(/[\d,.\s]+/)
      if (match) {
        totalInvestment = parseFloat(match[0].replace(/[,\s]/g, ''))
      } else {
        totalInvestment = (amount * price_buy) + (commission || 0)
      }
    } else {
      totalInvestment = (amount * price_buy) + (commission || 0)
    }
    
    const currentValue = current_value || (amount * effectiveCurrentPrice)
    const currentPnL = pnl || (currentValue - totalInvestment)
    const currentPnLPercent = pnl_percent || ((currentPnL / totalInvestment) * 100)
    
    return {
      totalInvestment,
      currentValue,
      currentPnL,
      currentPnLPercent,
      isProfit: currentPnL > 0
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>
            {alert ? 'Edit Price Alert' : `Create Alert for ${presetSymbol || selectedSymbol || 'Crypto'}`}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            {/* Investment Information */}
            {portfolioItem && (() => {
              const investment = calculateInvestmentPnL()
              if (!investment) return null
              
              return (
                <div className="bg-gray-50 p-3 rounded-lg">
                  <div className="text-sm font-medium text-gray-700 mb-2">Your Investment</div>
                  <div className="flex justify-between items-center text-xs">
                    <div className="flex space-x-4">
                      <div>
                        <span className="text-gray-500">Invested:</span>
                        <div className="font-medium">{formatCurrencyRounded(investment.totalInvestment)}</div>
                      </div>
                      <div>
                        <span className="text-gray-500">Current:</span>
                        <div className="font-medium">{formatCurrencyRounded(investment.currentValue)}</div>
                      </div>
                      <div>
                        <span className="text-gray-500">Buy:</span>
                        <div className="font-medium">{formatCurrency(portfolioItem.price_buy)}</div>
                      </div>
                      <div>
                        <span className="text-gray-500">Now:</span>
                        <div className="font-medium">{formatCurrency(currentPrice || 0)}</div>
                      </div>
                    </div>
                    <div className={`px-6 py-1 rounded text-xs font-medium ${
                      investment.isProfit ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}>
                      {investment.isProfit ? '📈' : '📉'} {formatCurrencyRounded(Math.abs(investment.currentPnL))} ({investment.currentPnLPercent.toFixed(1)}%)
                    </div>
                  </div>
                </div>
              )
            })()}

            {/* Symbol Selection - only show when no preset symbol */}
            {!presetSymbol && !alert && (
              <CryptoSearchSelect
                value={selectedSymbol}
                onValueChange={(value) => {
                  setSelectedSymbol(value)
                  setFormData(prev => ({ ...prev, symbol: value }))
                }}
                onSymbolSelect={(symbol) => {
                  setSelectedCryptoSymbol(symbol)
                  setSelectedSymbol(symbol.symbol)
                  setFormData(prev => ({ ...prev, symbol: symbol.symbol }))
                  fetchCurrentPrice(symbol.symbol)
                }}
                placeholder="Type to search cryptocurrencies..."
                disabled={loading}
              />
            )}

            {/* Price Input - Manual entry when no current price available */}
            {!currentPrice && !selectedCurrentPrice && selectedSymbol && (
              <div className="space-y-2">
                <Label htmlFor="threshold_price">Threshold Price ({selectedCurrency})</Label>
                <Input
                  id="threshold_price"
                  type="text"
                  value={formattedThresholdPrice}
                  onChange={(e) => {
                    const value = parseFormattedNumber(e.target.value)
                    if (!isNaN(value)) {
                      setThresholdPrice(value)
                      setFormattedThresholdPrice(formatNumberWithSpaces(value))
                      setFormData(prev => ({ 
                        ...prev, 
                        threshold_price: value.toString() 
                      }))
                    } else if (e.target.value === '') {
                      setThresholdPrice(0)
                      setFormattedThresholdPrice('')
                      setFormData(prev => ({ 
                        ...prev, 
                        threshold_price: '0' 
                      }))
                    }
                  }}
                  placeholder="Enter threshold price"
                />
                <div className="text-xs text-muted-foreground">
                  Enter the price at which you want to be alerted
                </div>
              </div>
            )}

            {/* Current Price Display for Create Alert */}
            {(currentPrice || selectedCurrentPrice) && selectedSymbol && !presetSymbol && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm text-blue-600 font-medium">
                      {presetSymbol || selectedSymbol || 'Crypto'} Current Price
                    </div>
                    <div className="text-2xl font-bold text-blue-800">
                      {formatCurrency(currentPrice || selectedCurrentPrice)}
                    </div>
                  </div>
                  {loadingPrice && (
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                  )}
                </div>
              </div>
            )}

            {/* Price Slider */}
            {(currentPrice || selectedCurrentPrice) && priceRange.min !== priceRange.max && (
              <div className="space-y-2">
                <div className="space-y-2">
                  {/* Price Range Display */}
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>{formatCurrency(priceRange.min)}</span>
                    <span className="font-medium text-green-600">Current: {formatCurrency(currentPrice || selectedCurrentPrice)}</span>
                    <span>{formatCurrency(priceRange.max)}</span>
                  </div>
                  
                  {/* Slider */}
                  <div className="relative">
                  <input
                    type="range"
                    min={priceRange.min}
                    max={priceRange.max}
                    step={(priceRange.max - priceRange.min) / 1000}
                    value={thresholdPrice}
                    onChange={(e) => handleSliderChange(parseFloat(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer slider"
                      style={{
                        background: (() => {
                          const priceDiff = calculatePriceDifference()
                          if (!priceDiff) {
                            return `linear-gradient(to right, 
                              ${formData.alert_type === 'ABOVE' ? '#10b981' : '#ef4444'} 0%, 
                              ${formData.alert_type === 'ABOVE' ? '#10b981' : '#ef4444'} ${getSliderPosition()}%, 
                              #e5e7eb ${getSliderPosition()}%, 
                              #e5e7eb 100%)`
                          }
                          const color = priceDiff.isAbove ? '#10b981' : '#ef4444'
                          return `linear-gradient(to right, 
                            ${color} 0%, 
                            ${color} ${getSliderPosition()}%, 
                            #e5e7eb ${getSliderPosition()}%, 
                            #e5e7eb 100%)`
                        })()
                      }}
                    />
                    {/* Current price marker */}
                    <div 
                      className="absolute top-0 w-1 h-2 bg-green-600 rounded-full transform -translate-x-1/2"
                      style={{ left: `${(((currentPrice || selectedCurrentPrice) - priceRange.min) / (priceRange.max - priceRange.min)) * 100}%` }}
                    />
                  </div>
                  
                  {/* Selected threshold display */}
                  <div className="text-center">
                    <div className={`inline-block px-3 py-1 rounded text-sm font-medium ${
                      (() => {
                        const priceDiff = calculatePriceDifference()
                        if (!priceDiff) {
                          return formData.alert_type === 'ABOVE' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                        }
                        return priceDiff.isAbove ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                      })()
                    }`}>
                      <input
                        type="text"
                        value={formattedThresholdPrice}
                        onChange={(e) => {
                          const value = parseFormattedNumber(e.target.value)
                          if (!isNaN(value)) {
                            setThresholdPrice(value)
                            setFormattedThresholdPrice(formatNumberWithSpaces(value))
                            setFormData(prev => ({ 
                              ...prev, 
                              threshold_price: value.toString() 
                            }))
                          } else if (e.target.value === '') {
                            setThresholdPrice(0)
                            setFormattedThresholdPrice('')
                            setFormData(prev => ({ 
                              ...prev, 
                              threshold_price: '0' 
                            }))
                          }
                        }}
                        className="bg-transparent border-none outline-none text-center font-medium w-32"
                        style={{
                          color: 'inherit'
                        }}
                      />
                    </div>
                    
                    {/* Price Difference Display */}
                    {(() => {
                      const priceDiff = calculatePriceDifference()
                      if (!priceDiff) return null
                      
                      return (
                        <div className={`text-xs mt-2 px-2 py-1 rounded ${
                          priceDiff.isAbove ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                        }`}>
                          {priceDiff.isAbove ? '📈' : '📉'} {priceDiff.isAbove ? 'Above' : 'Below'} current price: {Math.abs(priceDiff.percentageChange).toFixed(1)}% ({formatCurrency(Math.abs(priceDiff.priceChange))})
                        </div>
                      )
                    })()}
                    
                    {/* P&L Calculation - only show if we have portfolio item */}
                    {(() => {
                      const investmentPnL = calculateInvestmentBasedPnL()
                      if (!investmentPnL) return null
                      
                      return (
                        <div className={`text-xs mt-2 px-2 py-1 rounded ${
                          investmentPnL.isProfit ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                        }`}>
                          {investmentPnL.isProfit ? '📈' : '📉'} {investmentPnL.isProfit ? 'Gain' : 'Loss'}: {investmentPnL.investmentPercentageChange.toFixed(1)}% ({formatCurrency(Math.abs(investmentPnL.investmentChange))} from invested)
                        </div>
                      )
                    })()}
                  </div>
                </div>
              </div>
            )}


            {/* Alert Type Selection */}
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <label className={`flex items-center justify-center space-x-2 p-2 border rounded-lg cursor-pointer transition-colors ${
                  formData.alert_type === 'BELOW' 
                    ? 'bg-red-100 border-red-300 hover:bg-red-200' 
                    : 'bg-gray-50 border-gray-300 hover:bg-gray-100'
                }`}>
                  <input
                    type="radio"
                    value="BELOW"
                    checked={formData.alert_type === 'BELOW'}
                    onChange={(e) => handleChange('alert_type', e.target.value)}
                    className="text-red-500"
                  />
                  <span className={`text-sm font-medium ${
                    formData.alert_type === 'BELOW' ? 'text-red-800' : 'text-gray-600'
                  }`}>
                    Below
                  </span>
                </label>
                <label className={`flex items-center justify-center space-x-2 p-2 border rounded-lg cursor-pointer transition-colors ${
                  formData.alert_type === 'ABOVE' 
                    ? 'bg-green-100 border-green-300 hover:bg-green-200' 
                    : 'bg-gray-50 border-gray-300 hover:bg-gray-100'
                }`}>
                  <input
                    type="radio"
                    value="ABOVE"
                    checked={formData.alert_type === 'ABOVE'}
                    onChange={(e) => handleChange('alert_type', e.target.value)}
                    className="text-green-500"
                  />
                  <span className={`text-sm font-medium ${
                    formData.alert_type === 'ABOVE' ? 'text-green-800' : 'text-gray-600'
                  }`}>
                    Above
                  </span>
                </label>
              </div>
            </div>


            {/* Message Input */}
            <div className="space-y-2">
              <Input
                id="message"
                value={formData.message}
                onChange={(e) => handleChange('message', e.target.value)}
                placeholder={`${presetSymbol || selectedSymbol || formData.symbol || 'Crypto'} alert triggered!`}
              />
              <div className="text-xs text-muted-foreground">
                This message will be sent to Telegram when the alert triggers
              </div>
            </div>
          </div>
          
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? 'Saving...' : (alert ? 'Update Alert' : 'Create Alert')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
