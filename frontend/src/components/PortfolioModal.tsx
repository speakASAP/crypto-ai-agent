'use client'

import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { PortfolioItem, PortfolioCreate, PortfolioUpdate, Currency } from '@/types'

interface PortfolioModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: (item: PortfolioCreate | PortfolioUpdate) => Promise<void>
  item?: PortfolioItem | null
  selectedCurrency: Currency
}

export function PortfolioModal({ isOpen, onClose, onSave, item, selectedCurrency }: PortfolioModalProps) {
  // Currency to locale mapping for proper symbol display
  const currencyToLocale: Record<string, string> = {
    'USD': 'en-US',
    'EUR': 'de-DE', 
    'CZK': 'cs-CZ'
  }

  const [formData, setFormData] = useState({
    symbol: '',
    amount: '',
    price_buy: '',
    purchase_date: '',
    base_currency: selectedCurrency,
    source: '',
    commission: '0',
    total_investment_text: ''
  })

  // Helper function to parse total investment text
  const parseTotalInvestmentText = (text: string): number | null => {
    if (!text) return null
    // Remove currency symbols and parse numeric value
    const cleaned = text.replace(/[$,€\sKč£¥]/g, '').replace(/,/g, '')
    const parsed = parseFloat(cleaned)
    return isNaN(parsed) ? null : parsed
  }

  // Helper function to format total investment text with currency symbol
  const formatTotalInvestmentText = (amount: number, currency: string): string => {
    if (!amount || amount === 0) return `0 ${currency}`
    
    // Format number with commas for thousands
    const formatted_amount = amount >= 1 
      ? amount.toLocaleString('en-US', { maximumFractionDigits: 0 })
      : amount.toFixed(8).replace(/\.?0+$/, '')
    
    // Add currency symbol
    const currency_symbols: Record<string, string> = {
      "USD": "$",
      "EUR": "€",
      "CZK": "Kč",
      "GBP": "£",
      "JPY": "¥"
    }
    
    const symbol = currency_symbols[currency] || currency
    return symbol in ["$", "€", "£", "¥"] ? `${symbol}${formatted_amount}` : `${formatted_amount} ${symbol}`
  }

  // Track if user is actively editing total_investment_text field
  const [isEditingTotalInvestment, setIsEditingTotalInvestment] = useState(false)

  // Calculate total investment (amount * price_buy + commission)
  const totalInvestment = React.useMemo(() => {
    const amount = parseFloat(formData.amount) || 0
    const price = parseFloat(formData.price_buy) || 0
    const commission = parseFloat(formData.commission) || 0
    return (amount * price) + commission
  }, [formData.amount, formData.price_buy, formData.commission])

  // Auto-calculate total investment when amount, price, or commission change
  useEffect(() => {
    if (isEditingTotalInvestment) return // Don't auto-update if user is editing this field
    
    const amount = parseFloat(formData.amount) || 0
    const price = parseFloat(formData.price_buy) || 0
    const commission = parseFloat(formData.commission) || 0
    
    // Only update if we have valid values
    if (amount > 0 && price > 0) {
      const calculatedTotal = (amount * price) + commission
      const formattedTotal = formatTotalInvestmentText(calculatedTotal, formData.base_currency)
      
      if (formattedTotal !== formData.total_investment_text) {
        setFormData(prev => ({ ...prev, total_investment_text: formattedTotal }))
      }
    }
  }, [formData.amount, formData.price_buy, formData.commission, formData.base_currency, formData.total_investment_text, isEditingTotalInvestment])

  // Auto-calculate buy price from total investment when user edits total investment
  useEffect(() => {
    // Only calculate buy price if user is actively editing total investment field
    if (!isEditingTotalInvestment) return

    const parsedTotalInvestment = parseTotalInvestmentText(formData.total_investment_text)
    if (parsedTotalInvestment && parsedTotalInvestment > 0 && formData.amount) {
      const amount = parseFloat(formData.amount) || 0
      // Total investment includes commission, so price = (total_investment - commission) / amount
      const commission = parseFloat(formData.commission) || 0
      const calculatedPrice = amount > 0 ? (parsedTotalInvestment - commission) / amount : 0
      if (calculatedPrice > 0) {
        setFormData(prev => {
          // Only update if the price has actually changed
          if (Math.abs(calculatedPrice - (parseFloat(prev.price_buy) || 0)) > 0.00000001) {
            return { ...prev, price_buy: calculatedPrice.toString() }
          }
          return prev
        })
      }
    }
  }, [formData.amount, formData.commission, formData.total_investment_text, isEditingTotalInvestment])

  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (item) {
      setFormData({
        symbol: item.symbol,
        amount: item.amount.toString(),
        price_buy: item.price_buy.toString(),
        purchase_date: item.purchase_date || '',
        base_currency: item.base_currency as 'USD' | 'EUR' | 'CZK',
        source: item.source || '',
        commission: item.commission.toString(),
        total_investment_text: item.total_investment_text || ''
      })
    } else {
      // Set today's date as default for new items
      const today = new Date().toISOString().split('T')[0]
      setFormData({
        symbol: '',
        amount: '',
        price_buy: '',
        purchase_date: today,
        base_currency: selectedCurrency,
        source: '',
        commission: '0',
        total_investment_text: ''
      })
    }
  }, [item, selectedCurrency, isOpen])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // Validate: need either price_buy or total_investment_text
    if (!formData.price_buy && !formData.total_investment_text) {
      alert('Please enter either Buy Price or Total Investment')
      return
    }

    setLoading(true)

    try {
      const data = {
        ...formData,
        amount: parseFloat(formData.amount),
        price_buy: formData.price_buy ? parseFloat(formData.price_buy) : 0,
        commission: parseFloat(formData.commission)
      }

      await onSave(data)
      onClose()
    } catch (error) {
      console.error('Error saving portfolio item:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[850px]">
        <DialogHeader>
          <DialogTitle>
            {item ? 'Edit Portfolio Item' : 'Add New Portfolio Item'}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            {/* Administrative Info Section */}
            <div className="space-y-4">
              {/* Top Row: Symbol (narrow), Currency (narrow), Purchase Date, Source/Exchange */}
              <div className="grid grid-cols-[120px_110px_1fr_1fr] gap-4">
                <div className="space-y-2">
                  <Label htmlFor="symbol">Symbol</Label>
                  <Input
                    id="symbol"
                    value={formData.symbol}
                    onChange={(e) => handleChange('symbol', e.target.value.toUpperCase())}
                    placeholder="BTC"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="base_currency">Currency</Label>
                  <select
                    id="base_currency"
                    value={formData.base_currency}
                    onChange={(e) => handleChange('base_currency', e.target.value)}
                    className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                    <option value="CZK">CZK</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="purchase_date">Purchase Date</Label>
                  <Input
                    id="purchase_date"
                    type="date"
                    value={formData.purchase_date}
                    onChange={(e) => handleChange('purchase_date', e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="source">Source/Exchange</Label>
                  <Input
                    id="source"
                    value={formData.source}
                    onChange={(e) => handleChange('source', e.target.value)}
                    placeholder="Binance, Coinbase, etc."
                  />
                </div>
              </div>
            </div>

            {/* Finance Section */}
            <div className="space-y-4 border-t pt-4">
              {/* Amount and Buy Price */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="amount">Amount</Label>
                  <Input
                    id="amount"
                    type="number"
                    step="0.00000001"
                    value={formData.amount}
                    onChange={(e) => handleChange('amount', e.target.value)}
                    placeholder="0.50000000"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="price_buy">Buy Price</Label>
                  <Input
                    id="price_buy"
                    type="number"
                    step="0.00000001"
                    value={formData.price_buy}
                    onChange={(e) => handleChange('price_buy', e.target.value)}
                    placeholder="30000.00000000"
                  />
                  <div className="text-sm text-gray-600">
                    Leave empty and enter Total Investment to calculate automatically
                  </div>
                </div>
              </div>

              {/* Commission and Total Investment */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="commission">Commission</Label>
                  <Input
                    id="commission"
                    type="number"
                    step="0.00000001"
                    value={formData.commission}
                    onChange={(e) => handleChange('commission', e.target.value)}
                    placeholder="0.00000000"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="total_investment_text">Total Investment</Label>
                  <Input
                    id="total_investment_text"
                    value={formData.total_investment_text}
                    onChange={(e) => handleChange('total_investment_text', e.target.value)}
                    onFocus={() => setIsEditingTotalInvestment(true)}
                    onBlur={() => setIsEditingTotalInvestment(false)}
                    placeholder="e.g., $15,015 or €4,200 or 50,000 Kč"
                  />
                  <div className="text-sm text-gray-600">
                    Enter the total amount you invested
                  </div>
                </div>
              </div>

              {/* Calculated Total Investment Display */}
              <div className="space-y-2">
                <Label htmlFor="calculated_total">Calculated Total Investment</Label>
                <div className="p-3 bg-gray-50 rounded-md border">
                  <div className="text-lg font-semibold">
                    {totalInvestment > 0 ? 
                      new Intl.NumberFormat(currencyToLocale[formData.base_currency] || 'en-US', {
                        style: 'currency',
                        currency: formData.base_currency,
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 8
                      }).format(totalInvestment) : 
                      'Enter amount and price to calculate'
                    }
                  </div>
                  <div className="text-sm text-gray-600">
                    (Amount × Price + Commission)
                  </div>
                </div>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? 'Saving...' : (item ? 'Update' : 'Add')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
