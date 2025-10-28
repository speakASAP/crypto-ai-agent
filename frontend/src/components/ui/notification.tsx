'use client'

import { useEffect, useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { AlertCircle, CheckCircle, Info, X, AlertTriangle } from 'lucide-react'

export type NotificationType = 'success' | 'error' | 'warning' | 'info'

export interface Notification {
  id: string
  message: string
  type: NotificationType
  duration?: number
}

interface NotificationProps {
  notification: Notification | null
  onClose: () => void
}

export function NotificationDialog({ notification, onClose }: NotificationProps) {
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    if (notification) {
      setIsVisible(true)
      
      // Auto-dismiss after duration (default 5 seconds for alerts, 3 seconds for others)
      const duration = notification.duration ?? (notification.type === 'error' ? 5000 : 3000)
      
      const timer = setTimeout(() => {
        setIsVisible(false)
        setTimeout(onClose, 200) // Wait for fade out animation
      }, duration)

      return () => clearTimeout(timer)
    }
  }, [notification, onClose])

  if (!notification) return null

  const handleClose = () => {
    setIsVisible(false)
    setTimeout(onClose, 200) // Wait for fade out animation
  }

  const getIcon = () => {
    switch (notification.type) {
      case 'success':
        return <CheckCircle className="h-6 w-6 text-green-600" />
      case 'error':
        return <AlertCircle className="h-6 w-6 text-red-600" />
      case 'warning':
        return <AlertTriangle className="h-6 w-6 text-yellow-600" />
      case 'info':
        return <Info className="h-6 w-6 text-blue-600" />
      default:
        return <Info className="h-6 w-6 text-gray-600" />
    }
  }

  const getTitle = () => {
    switch (notification.type) {
      case 'success':
        return 'Success'
      case 'error':
        return 'Error'
      case 'warning':
        return 'Warning'
      case 'info':
        return 'Information'
      default:
        return 'Notification'
    }
  }

  const getColorClass = () => {
    switch (notification.type) {
      case 'success':
        return 'border-green-300 bg-green-50'
      case 'error':
        return 'border-red-300 bg-red-50'
      case 'warning':
        return 'border-yellow-300 bg-yellow-50'
      case 'info':
        return 'border-blue-300 bg-blue-50'
      default:
        return 'border-gray-300 bg-gray-50'
    }
  }

  return (
    <Dialog open={isVisible} onOpenChange={handleClose}>
      <DialogContent 
        className={`sm:max-w-[425px] ${getColorClass()}`}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            {getIcon()}
            <span className="capitalize">{getTitle()}</span>
          </DialogTitle>
        </DialogHeader>
        <div className="py-4">
          <p className="text-sm text-gray-700 whitespace-pre-line">
            {notification.message}
          </p>
        </div>
        <div className="flex justify-end">
          <Button 
            onClick={handleClose} 
            variant="outline" 
            size="sm"
            className="w-full sm:w-auto"
          >
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

