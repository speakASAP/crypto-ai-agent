'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { PriceAlert, PriceAlertCreate, PriceAlertUpdate } from '@/types'

interface AlertModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: (alert: PriceAlertCreate | PriceAlertUpdate) => Promise<void>
  alert?: PriceAlert | null
}

export function AlertModal({ isOpen, onClose, onSave, alert }: AlertModalProps) {
  const [formData, setFormData] = useState({
    symbol: '',
    threshold_price: '',
    alert_type: 'above',
    message: ''
  })

  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (alert) {
      setFormData({
        symbol: alert.symbol,
        threshold_price: alert.threshold_price.toString(),
        alert_type: alert.alert_type,
        message: alert.message || ''
      })
    } else {
      setFormData({
        symbol: '',
        threshold_price: '',
        alert_type: 'above',
        message: ''
      })
    }
  }, [alert, isOpen])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      const data = {
        ...formData,
        threshold_price: parseFloat(formData.threshold_price)
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

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>
            {alert ? 'Edit Price Alert' : 'Create New Price Alert'}
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
                <Label htmlFor="threshold_price">Threshold Price</Label>
                <Input
                  id="threshold_price"
                  type="number"
                  step="0.01"
                  value={formData.threshold_price}
                  onChange={(e) => handleChange('threshold_price', e.target.value)}
                  placeholder="50000"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="alert_type">Alert Type</Label>
              <Select value={formData.alert_type} onValueChange={(value) => handleChange('alert_type', value)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="above">Price Above</SelectItem>
                  <SelectItem value="below">Price Below</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="message">Message (Optional)</Label>
              <Input
                id="message"
                value={formData.message}
                onChange={(e) => handleChange('message', e.target.value)}
                placeholder="Custom alert message"
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? 'Saving...' : (alert ? 'Update' : 'Create')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
