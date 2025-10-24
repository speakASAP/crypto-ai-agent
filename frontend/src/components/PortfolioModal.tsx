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

  // Calculate total investment (amount * price_buy + commission)
  const totalInvestment = React.useMemo(() => {
    const amount = parseFloat(formData.amount) || 0
    const price = parseFloat(formData.price_buy) || 0
    const commission = parseFloat(formData.commission) || 0
    return (amount * price) + commission
  }, [formData.amount, formData.price_buy, formData.commission])

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
      setFormData({
        symbol: '',
        amount: '',
        price_buy: '',
        purchase_date: '',
        base_currency: selectedCurrency,
        source: '',
        commission: '0',
        total_investment_text: ''
      })
    }
  }, [item, selectedCurrency, isOpen])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      const data = {
        ...formData,
        amount: parseFloat(formData.amount),
        price_buy: parseFloat(formData.price_buy),
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
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>
            {item ? 'Edit Portfolio Item' : 'Add New Portfolio Item'}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
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
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="price_buy">Buy Price</Label>
                <Input
                  id="price_buy"
                  type="number"
                  step="0.00000001"
                  value={formData.price_buy}
                  onChange={(e) => handleChange('price_buy', e.target.value)}
                  placeholder="30000.00000000"
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

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="source">Source/Exchange</Label>
                <Input
                  id="source"
                  value={formData.source}
                  onChange={(e) => handleChange('source', e.target.value)}
                  placeholder="Binance, Coinbase, etc."
                />
              </div>
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
            </div>

            {/* Total Investment Text Field */}
            <div className="space-y-2">
              <Label htmlFor="total_investment_text">Total Investment (Original Currency)</Label>
              <Input
                id="total_investment_text"
                value={formData.total_investment_text}
                onChange={(e) => handleChange('total_investment_text', e.target.value)}
                placeholder="e.g., $15,015 or €4,200 or 50,000 Kč"
              />
              <div className="text-sm text-gray-600">
                Enter the total amount you invested in the original currency (e.g., $15,015, €4,200, 50,000 Kč)
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
