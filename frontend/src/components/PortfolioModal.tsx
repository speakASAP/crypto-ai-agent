'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
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
  const [formData, setFormData] = useState({
    symbol: '',
    amount: '',
    price_buy: '',
    purchase_date: '',
    base_currency: selectedCurrency,
    source: '',
    commission: '0'
  })

  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (item) {
      setFormData({
        symbol: item.symbol,
        amount: item.amount.toString(),
        price_buy: item.price_buy.toString(),
        purchase_date: item.purchase_date || '',
        base_currency: item.base_currency,
        source: item.source || '',
        commission: item.commission.toString()
      })
    } else {
      setFormData({
        symbol: '',
        amount: '',
        price_buy: '',
        purchase_date: '',
        base_currency: selectedCurrency,
        source: '',
        commission: '0'
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
                  placeholder="0.5"
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
                  step="0.01"
                  value={formData.price_buy}
                  onChange={(e) => handleChange('price_buy', e.target.value)}
                  placeholder="30000"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="base_currency">Currency</Label>
                <Select value={formData.base_currency} onValueChange={(value) => handleChange('base_currency', value)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="USD">USD</SelectItem>
                    <SelectItem value="EUR">EUR</SelectItem>
                    <SelectItem value="CZK">CZK</SelectItem>
                  </SelectContent>
                </Select>
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
                  step="0.01"
                  value={formData.commission}
                  onChange={(e) => handleChange('commission', e.target.value)}
                  placeholder="0"
                />
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
