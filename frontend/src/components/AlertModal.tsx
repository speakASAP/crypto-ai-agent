'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { PriceAlert, PriceAlertCreate, PriceAlertUpdate, Currency } from '@/types'

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
    current_value?: number
    pnl?: number
    pnl_percent?: number
  }
}

export function AlertModal({ isOpen, onClose, onSave, alert, presetSymbol, currentPrice, selectedCurrency, portfolioItem }: AlertModalProps) {
  const [formData, setFormData] = useState({
    symbol: '',
    threshold_price: '',
    alert_type: 'ABOVE',
    message: ''
  })

  const [loading, setLoading] = useState(false)
  const [thresholdPrice, setThresholdPrice] = useState(0)
  const [priceRange, setPriceRange] = useState({ min: 0, max: 0 })

  useEffect(() => {
    if (alert) {
      setFormData({
        symbol: alert.symbol,
        threshold_price: alert.threshold_price.toString(),
        alert_type: alert.alert_type,
        message: alert.message || ''
      })
      setThresholdPrice(alert.threshold_price)
    } else if (presetSymbol && currentPrice) {
      setFormData({
        symbol: presetSymbol,
        threshold_price: currentPrice.toString(),
        alert_type: 'ABOVE',
        message: ''
      })
      setThresholdPrice(currentPrice)
      // Set price range to ±50% of current price
      const range = currentPrice * 0.5
      setPriceRange({
        min: Math.max(0, currentPrice - range),
        max: currentPrice + range
      })
    } else {
      setFormData({
        symbol: '',
        threshold_price: '',
        alert_type: 'ABOVE',
        message: ''
      })
      setThresholdPrice(0)
      setPriceRange({ min: 0, max: 0 })
    }
  }, [alert, presetSymbol, currentPrice, isOpen])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      const data = {
        symbol: presetSymbol || formData.symbol,
        threshold_price: parseFloat(formData.threshold_price),
        alert_type: formData.alert_type as 'ABOVE' | 'BELOW',
        message: formData.message
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

  const calculatePercentageChange = (threshold: number, current: number) => {
    if (current === 0) return 0
    return ((threshold - current) / current) * 100
  }

  const adjustThresholdByPercentage = (percentage: number) => {
    if (!currentPrice) return
    
    const adjustment = currentPrice * (percentage / 100)
    const newThreshold = currentPrice + adjustment
    const clampedThreshold = Math.max(priceRange.min, Math.min(priceRange.max, newThreshold))
    
    setThresholdPrice(clampedThreshold)
    setFormData(prev => ({ 
      ...prev, 
      threshold_price: clampedThreshold.toString() 
    }))
  }

  const handleSliderChange = (value: number) => {
    setThresholdPrice(value)
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
    if (!currentPrice || !thresholdPrice) return null
    
    const priceChange = thresholdPrice - currentPrice
    const percentageChange = (priceChange / currentPrice) * 100
    
    return {
      priceChange,
      percentageChange,
      isProfit: priceChange > 0
    }
  }

  const calculateInvestmentPnL = () => {
    if (!portfolioItem || !currentPrice) return null
    
    const { amount, price_buy, current_value, pnl, pnl_percent } = portfolioItem
    const totalInvestment = amount * price_buy
    const currentValue = current_value || (amount * currentPrice)
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
            {alert ? 'Edit Price Alert' : `Create Alert for ${presetSymbol || 'Crypto'}`}
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
                        <div className="font-medium">{formatCurrency(investment.totalInvestment)}</div>
                      </div>
                      <div>
                        <span className="text-gray-500">Current:</span>
                        <div className="font-medium">{formatCurrency(investment.currentValue)}</div>
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
                    <div className={`px-3 py-1 rounded text-xs font-medium ${
                      investment.isProfit ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}>
                      {investment.isProfit ? '📈' : '📉'} {formatCurrency(Math.abs(investment.currentPnL))} ({investment.currentPnLPercent.toFixed(1)}%)
                    </div>
                  </div>
                </div>
              )
            })()}


            {/* Price Slider */}
            {currentPrice && priceRange.min !== priceRange.max && (
              <div className="space-y-2">
                <div className="space-y-2">
                  {/* Price Range Display */}
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>{formatCurrency(priceRange.min)}</span>
                    <span className="font-medium text-green-600">Current: {formatCurrency(currentPrice)}</span>
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
                        background: `linear-gradient(to right, 
                          ${formData.alert_type === 'ABOVE' ? '#10b981' : '#ef4444'} 0%, 
                          ${formData.alert_type === 'ABOVE' ? '#10b981' : '#ef4444'} ${getSliderPosition()}%, 
                          #e5e7eb ${getSliderPosition()}%, 
                          #e5e7eb 100%)`
                      }}
                    />
                    {/* Current price marker */}
                    <div 
                      className="absolute top-0 w-1 h-2 bg-green-600 rounded-full transform -translate-x-1/2"
                      style={{ left: `${((currentPrice - priceRange.min) / (priceRange.max - priceRange.min)) * 100}%` }}
                    />
                  </div>
                  
                  {/* Selected threshold display */}
                  <div className="text-center">
                    <div className={`inline-block px-3 py-1 rounded text-sm font-medium ${
                      formData.alert_type === 'ABOVE' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}>
                      {formatCurrency(thresholdPrice)}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {calculatePercentageChange(thresholdPrice, currentPrice).toFixed(2)}% from current
                    </div>
                    {/* P&L Calculation */}
                    {(() => {
                      const pnl = calculatePotentialPnL()
                      if (!pnl) return null
                      
                      return (
                        <div className={`text-xs mt-2 px-2 py-1 rounded ${
                          pnl.isProfit ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                        }`}>
                          {pnl.isProfit ? '📈' : '📉'} {pnl.isProfit ? 'Gain' : 'Loss'}: {formatCurrency(Math.abs(pnl.priceChange))} ({pnl.percentageChange.toFixed(1)}%)
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
                <label className="flex items-center justify-center space-x-2 p-2 border rounded-lg cursor-pointer hover:bg-gray-50">
                  <input
                    type="radio"
                    value="BELOW"
                    checked={formData.alert_type === 'BELOW'}
                    onChange={(e) => handleChange('alert_type', e.target.value)}
                    className="text-red-500"
                  />
                  <span className={`px-3 py-2 rounded text-sm font-medium ${formData.alert_type === 'BELOW' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-600'}`}>
                    Below
                  </span>
                </label>
                <label className="flex items-center justify-center space-x-2 p-2 border rounded-lg cursor-pointer hover:bg-gray-50">
                  <input
                    type="radio"
                    value="ABOVE"
                    checked={formData.alert_type === 'ABOVE'}
                    onChange={(e) => handleChange('alert_type', e.target.value)}
                    className="text-green-500"
                  />
                  <span className={`px-3 py-2 rounded text-sm font-medium ${formData.alert_type === 'ABOVE' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}`}>
                    Above
                  </span>
                </label>
              </div>
            </div>

            {/* Manual Price Input */}
            <div className="space-y-2">
              <Input
                id="threshold_price"
                type="number"
                step={currentPrice ? (priceRange.max - priceRange.min) / 10000 : 0.0001}
                value={formData.threshold_price}
                onChange={(e) => {
                  const value = parseFloat(e.target.value)
                  if (!isNaN(value)) {
                    setThresholdPrice(value)
                  }
                  handleChange('threshold_price', e.target.value)
                }}
                placeholder="50000"
                required
              />
            </div>

            {/* Message Input */}
            <div className="space-y-2">
              <Input
                id="message"
                value={formData.message}
                onChange={(e) => handleChange('message', e.target.value)}
                placeholder={`${presetSymbol || formData.symbol} alert triggered!`}
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
